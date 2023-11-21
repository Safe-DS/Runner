import queue
import multiprocessing
import threading
import json
import typing
import runpy
from multiprocessing.managers import SyncManager

import simple_websocket
import stack_data
import logging

from safeds_runner.server.module_manager import InMemoryFinder

# Multiprocessing
multiprocessing_manager: SyncManager | None = None
global_placeholder_map: dict = {}
global_messages_queue: queue.Queue | None = None
# Message Queue
websocket_target: simple_websocket.Server | None = None
messages_queue_thread: threading.Thread | None = None


def setup_pipeline_execution() -> None:
    """
    Prepares the runner for running Safe-DS pipelines.

    First structures shared between processes are created, after that a message queue handling thread is started in
    the main process. This allows receiving messages directly from one of the pipeline processes and relays information
    directly to the extension connection.
    """
    # Multiprocessing
    global multiprocessing_manager, global_messages_queue
    multiprocessing_manager = multiprocessing.Manager()
    global_messages_queue = multiprocessing_manager.Queue()
    # Message Queue
    global messages_queue_thread
    messages_queue_thread = threading.Thread(target=_handle_queue_messages, daemon=True)
    messages_queue_thread.start()


def _handle_queue_messages() -> None:
    global websocket_target
    while True:
        message = global_messages_queue.get()
        if websocket_target is not None:
            websocket_target.send(json.dumps(message))


def set_new_websocket_target(ws: simple_websocket.Server) -> None:
    """
    Inform the message queue handling thread that the websocket connection has changed.
    :param ws: New websocket connection
    """
    global websocket_target
    websocket_target = ws


class PipelineProcess:
    def __init__(self, code: dict[str, dict[str, str]], sdspackage: str, sdsmodule: str, sdspipeline: str,
                 execution_id: str, messages_queue: queue.Queue, placeholder_map: dict[str, typing.Any]):
        """
        Represents a process that executes a Safe-DS pipeline.
        :param code: A dictionary containing the code to be executed, in a virtual filesystem
        :param sdspackage: Safe-DS package name
        :param sdsmodule: Safe-DS module name
        :param sdspipeline: Safe-DS main pipeline name
        :param execution_id: Unique ID to identify this process
        :param messages_queue: A queue to write outgoing messages to
        :param placeholder_map: A map to save calculated placeholders in
        """
        self.code = code
        self.sdspackage = sdspackage
        self.sdsmodule = sdsmodule
        self.sdspipeline = sdspipeline
        self.id = execution_id
        self.messages_queue = messages_queue
        self.placeholder_map = placeholder_map
        self.process = multiprocessing.Process(target=self._execute, daemon=True)

    def _send_message(self, message_type: str, value: dict[typing.Any, typing.Any] | str) -> None:
        global global_messages_queue
        self.messages_queue.put({"type": message_type, "id": self.id, "data": value})

    def _send_exception(self, exception: BaseException) -> None:
        backtrace = get_backtrace_info(exception)
        self._send_message("runtime_error", {"message": exception.__str__(), "backtrace": backtrace})

    def save_placeholder(self, placeholder_name: str, value: typing.Any) -> None:
        """
        Save a calculated placeholder in the map
        :param placeholder_name: Name of the placeholder
        :param value: Actual value of the placeholder
        """
        self.placeholder_map[placeholder_name] = value

    def _execute(self) -> None:
        logging.info("Executing %s.%s.%s...", self.sdspackage, self.sdsmodule, self.sdspipeline)
        pipeline_finder = InMemoryFinder(self.code)
        pipeline_finder.attach()
        main_module = f"gen_{self.sdsmodule}_{self.sdspipeline}"
        try:
            runpy.run_module(main_module, run_name="__main__")  # TODO Is the Safe-DS-Package relevant here?
            self._send_message("progress", "done")
        except BaseException as error:
            self._send_exception(error)
        finally:
            pipeline_finder.detach()

    def execute(self) -> None:
        """
        Executes this pipeline in a newly created process and communicates results, progress and errors back
        to the main process
        """
        self.process.start()


def get_backtrace_info(error: BaseException) -> list[dict[str, typing.Any]]:
    """
    Creates a simplified backtrace from an exception
    :param error: Caught exception
    :return: List containing file and line information for each stack frame
    """
    backtrace_list = []
    for frame in stack_data.core.FrameInfo.stack_data(error.__traceback__):
        backtrace_list.append({"file": frame.filename, "line": int(frame.lineno)})
    return backtrace_list


def execute_pipeline(code: dict[str, dict[str, str]], sdspackage: str, sdsmodule: str, sdspipeline: str,
                     exec_id: str) -> None:
    """
    Runs a Safe-DS pipeline
    :param code: A dictionary containing the code to be executed, in a virtual filesystem
    :param sdspackage: Safe-DS package name
    :param sdsmodule: Safe-DS module name
    :param sdspipeline: Safe-DS main pipeline name
    :param exec_id: Unique ID to identify this execution
    """
    global multiprocessing_manager, global_messages_queue, global_placeholder_map
    if exec_id not in global_placeholder_map:
        global_placeholder_map[exec_id] = multiprocessing_manager.dict()
    process = PipelineProcess(code, sdspackage, sdsmodule, sdspipeline, exec_id, global_messages_queue,
                              global_placeholder_map[exec_id])
    process.execute()


def _get_placeholder_type(value: typing.Any):
    """
    :param value: any python object
    :return: Safe-DS name corresponding to the given python object instance
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
        return type(value).__name__
    return "Any"


def get_placeholder(exec_id: str, placeholder_name: str) -> typing.Tuple[str | None, typing.Any]:
    """
    Gets a placeholder type and value for an execution id and placeholder name
    :param exec_id: Unique id identifying execution
    :param placeholder_name: Name of the placeholder
    :return: Tuple containing placeholder type and placeholder value, or (None, None) if the placeholder does not exist
    """
    global global_placeholder_map
    if exec_id not in global_placeholder_map:
        return None, None
    if placeholder_name not in global_placeholder_map[exec_id]:
        return None, None
    value = global_placeholder_map[exec_id][placeholder_name]
    return _get_placeholder_type(value), value
