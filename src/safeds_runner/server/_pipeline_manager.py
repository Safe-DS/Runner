"""Module that contains the infrastructure for pipeline execution in child processes."""

import asyncio
import json
import linecache
import logging
import multiprocessing
import os
import queue
import runpy
import threading
import typing
from concurrent.futures import ProcessPoolExecutor
from functools import cached_property
from multiprocessing.managers import SyncManager
from pathlib import Path
from typing import Any

import stack_data

from ._memoization_map import MemoizationMap
from ._memoization_utils import (
    ExplicitIdentityWrapper,
    ExplicitIdentityWrapperLazy,
    _has_explicit_identity_memory,
    _is_deterministically_hashable,
    _is_not_primitive,
)
from ._messages import (
    Message,
    ProgramMessageData,
    create_placeholder_description,
    create_runtime_error_description,
    create_runtime_progress_done,
    message_type_placeholder_type,
    message_type_runtime_error,
    message_type_runtime_progress,
)
from ._module_manager import InMemoryFinder


class PipelineManager:
    """
    A PipelineManager handles the execution of pipelines and processing of results.

    This includes launching subprocesses and the communication between the
    subprocess and the main process using a shared message queue.
    """

    def __init__(self) -> None:
        """Create a new PipelineManager object, which is lazily started, when needed."""
        self._placeholder_map: dict = {}
        self._websocket_target: list[asyncio.Queue] = []

    @cached_property
    def _multiprocessing_manager(self) -> SyncManager:
        if multiprocessing.get_start_method() != "spawn":
            multiprocessing.set_start_method("spawn", force=True)
        return multiprocessing.Manager()

    @cached_property
    def _messages_queue(self) -> queue.Queue[Message]:
        return self._multiprocessing_manager.Queue()

    @cached_property
    def _process_pool(self) -> ProcessPoolExecutor:
        return ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context("spawn"))

    @cached_property
    def _messages_queue_thread(self) -> threading.Thread:
        return threading.Thread(target=self._handle_queue_messages, daemon=True, args=(asyncio.get_event_loop(),))

    @cached_property
    def _memoization_map(self) -> MemoizationMap:
        return MemoizationMap(self._multiprocessing_manager.dict(), self._multiprocessing_manager.dict())  # type: ignore[arg-type]

    def startup(self) -> None:
        """
        Prepare the runner for running Safe-DS pipelines.

        Firstly, structures shared between processes are lazily created.
        After that a message queue handling thread is started in the main process.
        This allows receiving messages directly from one of the pipeline processes and relaying information
        directly to the websocket connection (to the VS Code extension).

        This method should not be called during the bootstrap phase of the python interpreter, as it leads to a crash.
        """
        _mq = self._messages_queue  # Initialize it here before starting a thread to avoid potential race condition
        if not self._messages_queue_thread.is_alive():
            self._messages_queue_thread.start()
        # Ensure that pool is started
        _pool = self._process_pool

    def _handle_queue_messages(self, event_loop: asyncio.AbstractEventLoop) -> None:
        """
        Relay messages from pipeline processes to the currently connected websocket endpoint.

        Should be used in a dedicated thread.

        Parameters
        ----------
        event_loop:
            Event Loop that handles websocket connections.
        """
        try:
            while self._messages_queue is not None:
                message = self._messages_queue.get()
                message_encoded = json.dumps(message.to_dict())
                # only send messages to the same connection once
                for connection in set(self._websocket_target):
                    asyncio.run_coroutine_threadsafe(connection.put(message_encoded), event_loop)
        except BaseException as error:  # noqa: BLE001  # pragma: no cover
            logging.warning("Message queue terminated: %s", error.__repr__())  # pragma: no cover

    def connect(self, websocket_connection_queue: asyncio.Queue) -> None:
        """
        Add a websocket connection queue to relay event messages to, which are occurring during pipeline execution.

        Parameters
        ----------
        websocket_connection_queue:
            Message Queue for a websocket connection.
        """
        self._websocket_target.append(websocket_connection_queue)

    def disconnect(self, websocket_connection_queue: asyncio.Queue) -> None:
        """
        Remove a websocket target connection queue to no longer receive messages.

        Parameters
        ----------
        websocket_connection_queue:
            Message Queue for a websocket connection to be removed.
        """
        self._websocket_target.remove(websocket_connection_queue)

    def execute_pipeline(
        self,
        pipeline: ProgramMessageData,
        execution_id: str,
    ) -> None:
        """
        Run a Safe-DS pipeline.

        Parameters
        ----------
        pipeline:
            Message object that contains the information to run a pipeline.
        execution_id:
            Unique ID to identify this execution.
        """
        self.startup()
        if execution_id not in self._placeholder_map:
            self._placeholder_map[execution_id] = self._multiprocessing_manager.dict()
        process = PipelineProcess(
            pipeline,
            execution_id,
            self._messages_queue,
            self._placeholder_map[execution_id],
            self._memoization_map,
        )
        process.execute(self._process_pool)

    def get_placeholder(self, execution_id: str, placeholder_name: str) -> tuple[str | None, Any]:
        """
        Get a placeholder type and value for an execution id and placeholder name.

        Parameters
        ----------
        execution_id:
            Unique ID identifying the execution in which the placeholder was calculated.
        placeholder_name:
            Name of the placeholder.

        Returns
        -------
        placeholder:
            Tuple containing placeholder type and placeholder value, or (None, None) if the placeholder does not exist.
        """
        if execution_id not in self._placeholder_map:
            return None, None
        if placeholder_name not in self._placeholder_map[execution_id]:
            return None, None
        value = self._placeholder_map[execution_id][placeholder_name]
        if isinstance(value, ExplicitIdentityWrapper | ExplicitIdentityWrapperLazy):
            value = value.value
        return _get_placeholder_type(value), value

    def shutdown(self) -> None:
        """
        Shut down the multiprocessing manager to end the used subprocess.

        This should only be called if this PipelineManager is not intended to be reused again.
        """
        self._multiprocessing_manager.shutdown()
        self._process_pool.shutdown(wait=True, cancel_futures=True)


class PipelineProcess:
    """A process that executes a Safe-DS pipeline."""

    def __init__(
        self,
        pipeline: ProgramMessageData,
        execution_id: str,
        messages_queue: queue.Queue[Message],
        placeholder_map: dict[str, Any],
        memoization_map: MemoizationMap,
    ):
        """
        Create a new process which will execute the given pipeline, when started.

        Parameters
        ----------
        pipeline:
            Message object that contains the information to run a pipeline.
        execution_id:
            Unique ID to identify this process.
        messages_queue:
            A queue to write outgoing messages to.
        placeholder_map:
            A map to save calculated placeholders in.
        memoization_map:
            A map to save memoizable functions in.
        """
        self._pipeline = pipeline
        self._id = execution_id
        self._messages_queue = messages_queue
        self._placeholder_map = placeholder_map
        self._memoization_map = memoization_map

    def _send_message(self, message_type: str, value: dict[Any, Any] | str) -> None:
        self._messages_queue.put(Message(message_type, self._id, value))

    def _send_exception(self, exception: BaseException) -> None:
        backtrace = get_backtrace_info(exception)
        self._send_message(message_type_runtime_error, create_runtime_error_description(exception.__str__(), backtrace))

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
        self._placeholder_map[placeholder_name] = value
        self._send_message(
            message_type_placeholder_type,
            create_placeholder_description(placeholder_name, placeholder_type),
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
        logging.info(
            "Executing %s.%s.%s...",
            self._pipeline.main.modulepath,
            self._pipeline.main.module,
            self._pipeline.main.pipeline,
        )
        pipeline_finder = InMemoryFinder(self._pipeline.code)
        pipeline_finder.attach()
        main_module = f"gen_{self._pipeline.main.module}_{self._pipeline.main.pipeline}"
        # Populate current_pipeline global, so child process can save placeholders in correct location
        globals()["current_pipeline"] = self

        if self._pipeline.cwd is not None:
            os.chdir(self._pipeline.cwd)  # pragma: no cover

        try:
            runpy.run_module(
                (
                    main_module
                    if len(self._pipeline.main.modulepath) == 0
                    else f"{self._pipeline.main.modulepath}.{main_module}"
                ),
                run_name="__main__",
                alter_sys=True,
            )
            self._send_message(message_type_runtime_progress, create_runtime_progress_done())
        except BaseException as error:  # noqa: BLE001
            self._send_exception(error)
        finally:
            linecache.clearcache()
            pipeline_finder.detach()

    def _catch_subprocess_error(self, error: BaseException) -> None:
        # This is a callback to log an unexpected failure, executing this is never expected
        logging.exception("Pipeline process unexpectedly failed", exc_info=error)  # pragma: no cover

    def execute(self, pool: ProcessPoolExecutor) -> None:
        """
        Execute this pipeline in a process from the provided process pool.

        Results, progress and errors are communicated back to the main process.
        """
        future = pool.submit(self._execute)
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


def get_backtrace_info(error: BaseException) -> list[dict[str, Any]]:
    """
    Create a simplified backtrace from an exception.

    Parameters
    ----------
    error:
        Caught exception.

    Returns
    -------
    backtrace_info:
        List containing file and line information for each stack frame.
    """
    backtrace_list = []
    for frame in stack_data.core.FrameInfo.stack_data(error.__traceback__):
        backtrace_list.append({"file": frame.filename, "line": int(frame.lineno)})
    return backtrace_list


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
