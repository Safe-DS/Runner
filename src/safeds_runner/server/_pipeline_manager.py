"""Module that contains the infrastructure for pipeline execution in child processes."""

from __future__ import annotations

import linecache
import logging
import os
import runpy
import traceback
import typing
import warnings
from functools import cached_property
from typing import Any

from safeds.data.labeled.containers import TabularDataset

from safeds_runner.memoization._memoization_map import MemoizationMap
from safeds_runner.memoization._memoization_utils import (
    ExplicitIdentityWrapper,
    ExplicitIdentityWrapperLazy,
    _has_explicit_identity_memory,
    _is_deterministically_hashable,
    _is_not_primitive,
)

from ._module_manager import InMemoryFinder
from .messages._from_server import (
    StacktraceEntry,
    create_done_message,
    create_progress_message,
    create_runtime_error_message,
    create_runtime_warning_message,
)

if typing.TYPE_CHECKING:
    import queue

    from ._process_manager import ProcessManager
    from .messages._from_server import MessageFromServer
    from .messages._to_server import RunMessagePayload


class PipelineManager:
    """
    A PipelineManager handles the execution of pipelines and processing of results.

    This includes launching subprocesses and the communication between the
    subprocess and the main process using a shared message queue.
    """

    def __init__(self, process_manager: ProcessManager) -> None:
        self._process_manager = process_manager

    @cached_property
    def _memoization_map(self) -> MemoizationMap:
        return MemoizationMap(
            self._process_manager.create_shared_dict(),  # type: ignore[arg-type]
            self._process_manager.create_shared_dict(),  # type: ignore[arg-type]
        )

    async def execute_pipeline(self, payload: RunMessagePayload) -> None:
        """
        Run a Safe-DS pipeline.

        Parameters
        ----------
        payload:
            Information about the pipeline to run.
        """
        process = PipelineProcess(
            payload,
            self._process_manager.get_queue(),
            self._memoization_map,
        )
        await process.execute(self._process_manager)


class PipelineProcess:
    """A process that executes a Safe-DS pipeline."""

    def __init__(
        self,
        payload: RunMessagePayload,
        messages_queue: queue.Queue[MessageFromServer],
        memoization_map: MemoizationMap,
    ):
        """
        Create a new process which will execute the given pipeline, when started.

        Parameters
        ----------
        payload:
            Information about the pipeline to run.
        messages_queue:
            A queue to write outgoing messages to.
        memoization_map:
            A map to save results of memoizable functions in.
        """
        self._payload = payload
        self._messages_queue = messages_queue
        self._memoization_map = memoization_map

    def _send_message(self, message: MessageFromServer) -> None:
        self._messages_queue.put(message)

    def _send_warnings(self, warnings_: list[warnings.WarningMessage]) -> None:
        for warning in warnings_:
            self._send_message(
                create_runtime_warning_message(
                    run_id=self._payload.run_id,
                    message=str(warning.message),
                    stacktrace=[StacktraceEntry(file=warning.filename, line=warning.lineno)],
                ),
            )

    def _send_exception(self, exception: BaseException) -> None:
        self._send_message(
            create_runtime_error_message(
                run_id=self._payload.run_id,
                message=exception.__str__(),
                stacktrace=get_stacktrace(exception),
            ),
        )

    def report_placeholder_value(self, placeholder_name: str, value: Any) -> None:
        """
        Report the value of a placeholder.

        Parameters
        ----------
        placeholder_name:
            Name of the placeholder.
        value:
            Value of the placeholder.
        """
        from safeds.data.image.containers import Image

        if isinstance(value, Image):
            import torch

            value = Image(value._image_tensor, torch.device("cpu"))
        placeholder_type = _get_placeholder_type(value)
        if _is_deterministically_hashable(value) and _has_explicit_identity_memory(value):
            value = ExplicitIdentityWrapperLazy.existing(value)
        elif (
            not _is_deterministically_hashable(value)
            and _is_not_primitive(value)
            and _has_explicit_identity_memory(value)
        ):
            value = ExplicitIdentityWrapper.existing(value)
        # TODO
        # self._placeholder_map[placeholder_name] = value
        # self._send_message(
        #     message_type_placeholder_type,
        #     create_placeholder_description(placeholder_name, placeholder_type),
        # )

    def report_placeholder_computed(self, placeholder_name: str) -> None:
        """
        Report that a placeholder has been computed.

        Parameters
        ----------
        placeholder_name:
            Name of the placeholder.
        """
        self._send_message(
            create_progress_message(
                run_id=self._payload.run_id,
                placeholder_name=placeholder_name,
                percentage=100,
            ),
        )

    def get_memoization_map(self) -> MemoizationMap:
        """
        Get the shared memoization map.

        Returns
        -------
        memoization_map:
            Memoization Map
        """
        return self._memoization_map

    def _execute(self) -> None:
        logging.info("Executing %s...", self._payload.main_absolute_module_name)

        pipeline_finder = InMemoryFinder(self._payload.code)
        pipeline_finder.attach()
        # Populate current_pipeline global, so child process can save placeholders in correct location
        globals()["current_pipeline"] = self

        if self._payload.cwd is not None:
            os.chdir(self._payload.cwd)  # pragma: no cover

        try:
            with warnings.catch_warnings(record=True) as collected_warnings:
                runpy.run_module(
                    self._payload.main_absolute_module_name,
                    run_name="__main__",
                    alter_sys=True,
                )
                self._send_warnings(collected_warnings)
        except BaseException as error:  # noqa: BLE001
            self._send_exception(error)
        finally:
            self._send_message(create_done_message(self._payload.run_id))
            # Needed for `getSource` to work correctly when the process is reused
            linecache.clearcache()
            pipeline_finder.detach()

    def _catch_subprocess_error(self, error: BaseException) -> None:
        # This is a callback to log an unexpected failure, executing this is never expected
        logging.exception("Pipeline process unexpectedly failed", exc_info=error)  # pragma: no cover

    async def execute(self, process_manager: ProcessManager) -> None:
        """
        Execute this pipeline in a process from the provided process pool.

        Results, progress and errors are communicated back to the main process.
        """
        future = process_manager.submit(self._execute)
        exception = future.exception()
        if exception is not None:
            self._catch_subprocess_error(exception)  # pragma: no cover


# Pipeline process object visible in child process
current_pipeline: PipelineProcess | None = None


def get_stacktrace(error: BaseException) -> list[StacktraceEntry]:
    """
    Create a simplified stacktrace from an exception.

    Parameters
    ----------
    error:
        Caught exception.

    Returns
    -------
    backtrace_info:
        List containing file and line information for each stack frame.
    """
    frames = traceback.extract_tb(error.__traceback__)
    return [StacktraceEntry(file=frame.filename, line=int(frame.lineno)) for frame in reversed(list(frames))]


def _get_placeholder_type(value: Any) -> str:
    """
    Convert a python object to a Safe-DS type.

    Parameters
    ----------
    value:
        A python object.

    Returns
    -------
    placeholder_type:
        Safe-DS name corresponding to the given python object instance.
    """
    match value:
        case bool():
            return "Boolean"
        case float():
            return "Float"
        case int():
            return "Int"
        case str():
            return "String"
        case TabularDataset():
            return "Table"
        case object():
            object_name = type(value).__name__
            match object_name:
                case "function":
                    return "Callable"
                case "NoneType":
                    return "Null"
                case _:
                    return object_name
        case _:  # pragma: no cover
            return "Any"  # pragma: no cover


        # @sio.event
        # async def placeholder_query(_sid: str, payload: Any) -> None:
        #     try:
        #         placeholder_query_message = QueryMessage(**payload)
        #     except (TypeError, ValidationError):
        #         logging.exception("Invalid message data specified in: %s", payload)
        #         return
        #
        #     placeholder_type, placeholder_value = self._pipeline_manager.get_placeholder(
        #         placeholder_query_message.id,
        #         placeholder_query_message.data.name,
        #     )
        #
        #     if placeholder_type is None:
        #         # Send back empty type / value, to communicate that no placeholder exists (yet)
        #         # Use name from query to allow linking a response to a request on the peer
        #         data = json.dumps(create_placeholder_value(placeholder_query_message.data, "", ""))
        #         await sio.emit(message_type_placeholder_value, data, to=placeholder_query_message.id)
        #         return
        #
        #     try:
        #         data = json.dumps(
        #             create_placeholder_value(
        #                 placeholder_query_message.data,
        #                 placeholder_type,
        #                 placeholder_value,
        #             ),
        #             cls=SafeDsEncoder,
        #         )
        #     except TypeError:
        #         # if the value can't be encoded send back that the value exists but is not displayable
        #         data = json.dumps(
        #             create_placeholder_value(
        #                 placeholder_query_message.data,
        #                 placeholder_type,
        #                 "<Not displayable>",
        #             ),
        #         )
        #
        #     await sio.emit(message_type_placeholder_value, data, to=placeholder_query_message.id)



    # TODO: move into process that creates placeholder value messages
# def create_placeholder_value(placeholder_query: QueryMessageData, type_: str, value: Any) -> dict[str, Any]:
#     """
#     Create the message data of a placeholder value message containing name, type and the actual value.
#
#     If the query only requests a subset of the data and the placeholder type supports this,
#     the response will contain only a subset and the information about the subset.
#
#     Parameters
#     ----------
#     placeholder_query:
#         Query of the placeholder.
#     type_:
#         Type of the placeholder.
#     value:
#         Value of the placeholder.
#
#     Returns
#     -------
#     message_data:
#         Message data of "placeholder_value" messages.
#     """
#     import safeds.data.tabular.containers
#
#     message: dict[str, Any] = {"name": placeholder_query.name, "type": type_}
#     # Start Index >= 0
#     start_index = max(placeholder_query.window.begin if placeholder_query.window.begin is not None else 0, 0)
#     # End Index >= Start Index
#     end_index = (
#         (start_index + max(placeholder_query.window.size, 0)) if placeholder_query.window.size is not None else None
#     )
#     if isinstance(value, safeds.data.tabular.containers.Table) and (
#         placeholder_query.window.begin is not None or placeholder_query.window.size is not None
#     ):
#         max_index = value.number_of_rows
#         # End Index <= Number Of Rows
#         end_index = min(end_index, value.number_of_rows) if end_index is not None else None
#         value = value.slice_rows(start=start_index, end=end_index)
#         window_information: dict[str, int] = {"begin": start_index, "size": value.number_of_rows, "max": max_index}
#         message["window"] = window_information
#     message["value"] = value
#     return message
