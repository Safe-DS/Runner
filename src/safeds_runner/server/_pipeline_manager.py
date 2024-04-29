"""Module that contains the infrastructure for pipeline execution in child processes."""

from __future__ import annotations

import linecache
import logging
import os
import runpy
import typing
import warnings
from functools import cached_property
from pathlib import Path
from typing import Any

import stack_data

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

    def save_placeholder(self, placeholder_name: str, value: Any) -> None:
        """
        Save a calculated placeholder in the map.

        Parameters
        ----------
        placeholder_name:
            Name of the placeholder.
        value:
            Actual value of the placeholder.
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


def save_placeholder(placeholder_name: str, value: Any) -> None:
    """
    Save a placeholder for the current running pipeline.

    Parameters
    ----------
    placeholder_name:
        Name of the placeholder.
    value:
        Actual value of the placeholder.
    """
    if current_pipeline is not None:
        current_pipeline.save_placeholder(placeholder_name, value)


def memoized_static_call(
    fully_qualified_function_name: str,
    callable_: typing.Callable,
    positional_arguments: list[Any],
    keyword_arguments: dict[str, Any],
    hidden_arguments: list[Any],
) -> Any:
    """
    Call a function that can be memoized and save the result.

    If a function has been previously memoized, the previous result may be reused.

    Parameters
    ----------
    fully_qualified_function_name:
        Fully qualified function name
    callable_:
        Function that is called and memoized if the result was not found in the memoization map
    positional_arguments:
        List of positions arguments for the function
    keyword_arguments:
        Dictionary of keyword arguments for the function
    hidden_arguments:
        List of hidden arguments for the function. This is used for memoizing some impure functions.

    Returns
    -------
    result:
        The result of the specified function, if any exists
    """
    if current_pipeline is None:
        return None  # pragma: no cover

    memoization_map = current_pipeline.get_memoization_map()
    return memoization_map.memoized_function_call(
        fully_qualified_function_name,
        callable_,
        positional_arguments,
        keyword_arguments,
        hidden_arguments,
    )


def memoized_dynamic_call(
    receiver: Any,
    function_name: str,
    positional_arguments: list[Any],
    keyword_arguments: dict[str, Any],
    hidden_arguments: list[Any],
) -> Any:
    """
    Dynamically call a function that can be memoized and save the result.

    If a function has been previously memoized, the previous result may be reused.
    Dynamically calling in this context means, that if a callable is provided (e.g. if default parameters are set), it will be called.
    If no such callable is provided, the function name will be used to look up the function on the instance passed as the first parameter in the parameter list.

    Parameters
    ----------
    receiver : Any
        Instance the function should be called on
    function_name:
        Simple function name
    positional_arguments:
        List of positions arguments for the function
    keyword_arguments:
        Dictionary of keyword arguments for the function
    hidden_arguments:
        List of hidden parameters for the function. This is used for memoizing some impure functions.

    Returns
    -------
    result:
        The result of the specified function, if any exists
    """
    if current_pipeline is None:
        return None  # pragma: no cover

    fully_qualified_function_name = (
        receiver.__class__.__module__ + "." + receiver.__class__.__qualname__ + "." + function_name
    )

    member = getattr(receiver, function_name)
    callable_ = member.__func__

    memoization_map = current_pipeline.get_memoization_map()
    return memoization_map.memoized_function_call(
        fully_qualified_function_name,
        callable_,
        [receiver, *positional_arguments],
        keyword_arguments,
        hidden_arguments,
    )


@typing.overload
def file_mtime(filenames: str) -> int | None: ...


@typing.overload
def file_mtime(filenames: list[str]) -> list[int | None]: ...


def file_mtime(filenames: str | list[str]) -> int | None | list[int | None]:
    """
    Get the last modification timestamp of the provided file.

    Parameters
    ----------
    filenames:
        Names of the files

    Returns
    -------
    timestamps:
        Last modification timestamp or None for each provided file, depending on whether the file exists or not.
    """
    if isinstance(filenames, list):
        return [file_mtime(f) for f in filenames]

    try:
        return Path(filenames).stat().st_mtime_ns
    except FileNotFoundError:
        return None


@typing.overload
def absolute_path(filenames: str) -> str: ...


@typing.overload
def absolute_path(filenames: list[str]) -> list[str]: ...


def absolute_path(filenames: str | list[str]) -> str | list[str]:
    """
    Get the absolute path of the provided file.

    Parameters
    ----------
    filenames:
        Names of the files.

    Returns
    -------
    absolute_paths:
        Absolute paths of the provided files.
    """
    if isinstance(filenames, list):
        return [absolute_path(f) for f in filenames]

    return str(Path(filenames).resolve())


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
    frames = stack_data.core.FrameInfo.stack_data(error.__traceback__)
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
