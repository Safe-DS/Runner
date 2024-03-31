"""Module that contains the infrastructure for pipeline execution in child processes."""

import asyncio
import json
import logging
import multiprocessing
import queue
import runpy
import threading
import typing
from functools import cached_property
from multiprocessing.managers import SyncManager
from pathlib import Path
from typing import Any

import stack_data

from ._memoization_map import MemoizationMap
from ._messages import (
    Message,
    MessageDataProgram,
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

    def _handle_queue_messages(self, event_loop: asyncio.AbstractEventLoop) -> None:
        """
        Relay messages from pipeline processes to the currently connected websocket endpoint.

        Should be used in a dedicated thread.

        Parameters
        ----------
        event_loop : asyncio.AbstractEventLoop
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
        websocket_connection_queue : asyncio.Queue
            Message Queue for a websocket connection.
        """
        self._websocket_target.append(websocket_connection_queue)

    def disconnect(self, websocket_connection_queue: asyncio.Queue) -> None:
        """
        Remove a websocket target connection queue to no longer receive messages.

        Parameters
        ----------
        websocket_connection_queue : asyncio.Queue
            Message Queue for a websocket connection to be removed.
        """
        self._websocket_target.remove(websocket_connection_queue)

    def execute_pipeline(
        self,
        pipeline: MessageDataProgram,
        execution_id: str,
    ) -> None:
        """
        Run a Safe-DS pipeline.

        Parameters
        ----------
        pipeline : MessageDataProgram
            Message object that contains the information to run a pipeline.
        execution_id : str
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
        process.execute()

    def get_placeholder(self, execution_id: str, placeholder_name: str) -> tuple[str | None, Any]:
        """
        Get a placeholder type and value for an execution id and placeholder name.

        Parameters
        ----------
        execution_id : str
            Unique ID identifying the execution in which the placeholder was calculated.
        placeholder_name : str
            Name of the placeholder.

        Returns
        -------
        tuple[str | None, Any]
            Tuple containing placeholder type and placeholder value, or (None, None) if the placeholder does not exist.
        """
        if execution_id not in self._placeholder_map:
            return None, None
        if placeholder_name not in self._placeholder_map[execution_id]:
            return None, None
        value = self._placeholder_map[execution_id][placeholder_name]
        return _get_placeholder_type(value), value

    def shutdown(self) -> None:
        """
        Shut down the multiprocessing manager to end the used subprocess.

        This should only be called if this PipelineManager is not intended to be reused again.
        """
        self._multiprocessing_manager.shutdown()


class PipelineProcess:
    """A process that executes a Safe-DS pipeline."""

    def __init__(
        self,
        pipeline: MessageDataProgram,
        execution_id: str,
        messages_queue: queue.Queue[Message],
        placeholder_map: dict[str, Any],
        memoization_map: MemoizationMap,
    ):
        """
        Create a new process which will execute the given pipeline, when started.

        Parameters
        ----------
        pipeline : MessageDataProgram
            Message object that contains the information to run a pipeline.
        execution_id : str
            Unique ID to identify this process.
        messages_queue : queue.Queue[Message]
            A queue to write outgoing messages to.
        placeholder_map : dict[str, Any]
            A map to save calculated placeholders in.
        memoization_map : MemoizationMap
            A map to save memoizable functions in.
        """
        self._pipeline = pipeline
        self._id = execution_id
        self._messages_queue = messages_queue
        self._placeholder_map = placeholder_map
        self._memoization_map = memoization_map
        self._process = multiprocessing.Process(target=self._execute, daemon=True)

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
        placeholder_name : str
            Name of the placeholder.
        value : Any
            Actual value of the placeholder.
        """
        from safeds.data.image.containers import Image

        if isinstance(value, Image):
            import torch

            value = Image(value._image_tensor, torch.device("cpu"))
        self._placeholder_map[placeholder_name] = value
        placeholder_type = _get_placeholder_type(value)
        self._send_message(
            message_type_placeholder_type,
            create_placeholder_description(placeholder_name, placeholder_type),
        )

    def get_memoization_map(self) -> MemoizationMap:
        """
        Get the shared memoization map.

        Returns
        -------
        MemoizationMap
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
            pipeline_finder.detach()

    def execute(self) -> None:
        """
        Execute this pipeline in a newly created process.

        Results, progress and errors are communicated back to the main process.
        """
        self._process.start()


# Pipeline process object visible in child process
current_pipeline: PipelineProcess | None = None


def save_placeholder(placeholder_name: str, value: Any) -> None:
    """
    Save a placeholder for the current running pipeline.

    Parameters
    ----------
    placeholder_name : str
        Name of the placeholder.
    value : Any
        Actual value of the placeholder.
    """
    if current_pipeline is not None:
        current_pipeline.save_placeholder(placeholder_name, value)


def memoized_call(
    function_name: str,
    function_callable: typing.Callable,
    parameters: list[Any],
    hidden_parameters: list[Any],
) -> Any:
    """
    Call a function that can be memoized and save the result.

    If a function has been previously memoized, the previous result may be reused.

    Parameters
    ----------
    function_name : str
        Fully qualified function name
    function_callable : typing.Callable
        Function that is called and memoized if the result was not found in the memoization map
    parameters : list[Any]
        List of parameters for the function
    hidden_parameters : list[Any]
        List of hidden parameters for the function. This is used for memoizing some impure functions.

    Returns
    -------
    Any
        The result of the specified function, if any exists
    """
    if current_pipeline is None:
        return None  # pragma: no cover
    memoization_map = current_pipeline.get_memoization_map()
    return memoization_map.memoized_function_call(function_name, function_callable, parameters, hidden_parameters)


def file_mtime(filename: str) -> int | None:
    """
    Get the last modification timestamp of the provided file.

    Parameters
    ----------
    filename: str
        Name of the file

    Returns
    -------
    int | None
        Last modification timestamp if the provided file exists, otherwise None
    """
    try:
        return Path(filename).stat().st_mtime_ns
    except FileNotFoundError:
        return None


def get_backtrace_info(error: BaseException) -> list[dict[str, Any]]:
    """
    Create a simplified backtrace from an exception.

    Parameters
    ----------
    error : BaseException
        Caught exception.

    Returns
    -------
    list[dict[str, Any]]
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
    value : Any
        A python object.

    Returns
    -------
    str
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
