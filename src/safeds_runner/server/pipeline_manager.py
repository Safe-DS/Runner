"""Module that contains the infrastructure for pipeline execution in child processes."""

import json
import logging
import multiprocessing
import queue
import runpy
import threading
from multiprocessing.managers import SyncManager
from typing import Any

import simple_websocket
import stack_data

from safeds_runner.server.messages import (
    Message,
    MessageDataProgram,
    create_placeholder_description,
    create_runtime_error_description,
    create_runtime_progress_done,
    message_type_placeholder_type,
    message_type_runtime_error,
    message_type_runtime_progress,
)
from safeds_runner.server.module_manager import InMemoryFinder

# Multiprocessing
multiprocessing_manager: SyncManager | None = None
global_placeholder_map: dict = {}
global_messages_queue: queue.Queue[Message] | None = None
# Message Queue
websocket_target: simple_websocket.Server | None = None
messages_queue_thread: threading.Thread | None = None


def setup_pipeline_execution() -> None:
    """
    Prepare the runner for running Safe-DS pipelines.

    Firstly, structures shared between processes are created.
    After that a message queue handling thread is started in the main process.
    This allows receiving messages directly from one of the pipeline processes and relaying information
    directly to the websocket connection (to the VS Code extension).
    """
    # Multiprocessing
    global multiprocessing_manager, global_messages_queue  # noqa: PLW0603
    multiprocessing_manager = multiprocessing.Manager()
    global_messages_queue = multiprocessing_manager.Queue()
    # Message Queue
    global messages_queue_thread  # noqa: PLW0603
    messages_queue_thread = threading.Thread(target=_handle_queue_messages, daemon=True)
    messages_queue_thread.start()


def _handle_queue_messages() -> None:
    """
    Relay messages from pipeline processes to the currently connected websocket endpoint.

    Should be used in a dedicated thread.
    """
    try:
        while global_messages_queue is not None:
            message = global_messages_queue.get()
            if websocket_target is not None:
                websocket_target.send(json.dumps(message.to_dict()))
    except BaseException as error:  # noqa: BLE001  # pragma: no cover
        logging.warning("Message queue terminated: %s", error.__repr__())  # pragma: no cover


def set_new_websocket_target(ws: simple_websocket.Server) -> None:
    """
    Inform the message queue handling thread that the websocket connection has changed.

    Parameters
    ----------
    ws : simple_websocket.Server
        New websocket connection.
    """
    global websocket_target  # noqa: PLW0603
    websocket_target = ws


class PipelineProcess:
    """A process that executes a Safe-DS pipeline."""

    def __init__(
        self,
        pipeline: MessageDataProgram,
        execution_id: str,
        messages_queue: queue.Queue[Message],
        placeholder_map: dict[str, Any],
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
        """
        self.pipeline = pipeline
        self.id = execution_id
        self.messages_queue = messages_queue
        self.placeholder_map = placeholder_map
        self.process = multiprocessing.Process(target=self._execute, daemon=True)

    def _send_message(self, message_type: str, value: dict[Any, Any] | str) -> None:
        self.messages_queue.put(Message(message_type, self.id, value))

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
        self.placeholder_map[placeholder_name] = value
        placeholder_type = _get_placeholder_type(value)
        self._send_message(
            message_type_placeholder_type,
            create_placeholder_description(placeholder_name, placeholder_type),
        )

    def _execute(self) -> None:
        logging.info(
            "Executing %s.%s.%s...",
            self.pipeline.main.modulepath,
            self.pipeline.main.module,
            self.pipeline.main.pipeline,
        )
        pipeline_finder = InMemoryFinder(self.pipeline.code)
        pipeline_finder.attach()
        main_module = f"gen_{self.pipeline.main.module}_{self.pipeline.main.pipeline}"
        global current_pipeline  # noqa: PLW0603
        current_pipeline = self
        try:
            runpy.run_module(
                (
                    main_module
                    if len(self.pipeline.main.modulepath) == 0
                    else f"{self.pipeline.main.modulepath}.{main_module}"
                ),
                run_name="__main__",
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
        self.process.start()


# Current Pipeline
current_pipeline: PipelineProcess | None = None


def runner_save_placeholder(placeholder_name: str, value: Any) -> None:
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


def execute_pipeline(
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
    if global_placeholder_map is not None and global_messages_queue is not None and multiprocessing_manager is not None:
        if execution_id not in global_placeholder_map:
            global_placeholder_map[execution_id] = multiprocessing_manager.dict()
        process = PipelineProcess(
            pipeline,
            execution_id,
            global_messages_queue,
            global_placeholder_map[execution_id],
        )
        process.execute()


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
    if isinstance(value, bool):
        return "Boolean"
    if isinstance(value, float):
        return "Float"
    if isinstance(value, int):
        return "Int"
    if isinstance(value, str):
        return "String"
    if isinstance(value, object):
        object_name = type(value).__name__
        if object_name == "function":
            return "Callable"
        if object_name == "NoneType":
            return "Null"
        return object_name
    return "Any"  # pragma: no cover


def get_placeholder(execution_id: str, placeholder_name: str) -> tuple[str | None, Any]:
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
    if execution_id not in global_placeholder_map:
        return None, None
    if placeholder_name not in global_placeholder_map[execution_id]:
        return None, None
    value = global_placeholder_map[execution_id][placeholder_name]
    return _get_placeholder_type(value), value
