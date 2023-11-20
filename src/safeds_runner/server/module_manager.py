import importlib.abc
import multiprocessing
import threading
import queue
from abc import ABC
from importlib.machinery import ModuleSpec
import sys
import importlib.util
import types
import runpy
import logging
import typing
import json
import stack_data

# Multiprocessing
multiprocessing_manager = None
global_placeholder_map = {}
global_messages_queue: queue.Queue | None = None
# Threading
websocket_target = None
messages_queue_thread = None


def setup_multiprocessing():
    global multiprocessing_manager, global_messages_queue
    multiprocessing_manager = multiprocessing.Manager()
    global_messages_queue = multiprocessing_manager.Queue()


class InMemoryLoader(importlib.abc.SourceLoader, ABC):
    def __init__(self, code_bytes: bytes, filename: str):
        self.code_bytes = code_bytes
        self.filename = filename

    def get_data(self, path) -> bytes:
        return self.code_bytes

    def get_filename(self, fullname) -> str:
        return self.filename


class InMemoryFinder(importlib.abc.MetaPathFinder):
    def __init__(self, code: dict[str, dict[str, str]]):
        self.code = code
        self.allowed_packages = {key for key in code.keys()}
        self.imports_to_remove = set()
        for key in code.keys():
            while "." in key:
                key = key.rpartition(".")[0]
                self.allowed_packages.add(key)

    def find_spec(self, fullname: str, path=None, target: types.ModuleType | None = None) -> ModuleSpec | None:
        logging.debug(f"Find Spec: {fullname} {path} {target}")
        if fullname in self.allowed_packages:
            parent_package = importlib.util.spec_from_loader(fullname, loader=InMemoryLoader("".encode("utf-8"),
                                                                                             fullname.replace(".",
                                                                                                              "/")))
            if parent_package.submodule_search_locations is None:
                parent_package.submodule_search_locations = []
            parent_package.submodule_search_locations.append(fullname.replace(".", "/"))
            self.imports_to_remove.add(fullname)
            return parent_package
        module_path = fullname.split(".")
        if len(module_path) == 1 and "" in self.code and fullname in self.code[""]:
            self.imports_to_remove.add(fullname)
            return importlib.util.spec_from_loader(fullname,
                                                   loader=InMemoryLoader(self.code[""][fullname].encode("utf-8"),
                                                                         fullname.replace(".", "/")),
                                                   origin="")
        parent_package = ".".join(module_path[:-1])
        submodule_name = module_path[-1]
        if parent_package in self.code and submodule_name in self.code[parent_package]:
            self.imports_to_remove.add(fullname)
            return importlib.util.spec_from_loader(fullname,
                                                   loader=InMemoryLoader(
                                                       self.code[parent_package][submodule_name].encode("utf-8"),
                                                       fullname.replace(".", "/")),
                                                   origin=parent_package)
        return None

    def attach(self):
        sys.meta_path.append(self)

    def detach(self):
        # As modules should not be used from other modules, outside our pipeline,
        # it should be safe to just remove all newly imported modules
        for key in self.imports_to_remove:
            if key in sys.modules.keys():
                del sys.modules[key]
        sys.meta_path.remove(self)


class PipelineProcess:
    def __init__(self, code: dict[str, dict[str, str]], sdspackage: str, sdsmodule: str, sdspipeline: str,
                 execution_id: str, messages_queue: queue.Queue, placeholder_map: dict[str, typing.Any]):
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

    def _send_exception(self, exception: BaseException):
        backtrace = get_backtrace_info(exception)
        self._send_message("runtime_error", {"message": exception.__str__(), "backtrace": backtrace})

    def save_placeholder(self, placeholder_name: str, value: typing.Any) -> None:
        self.placeholder_map[placeholder_name] = value

    def _execute(self):
        logging.info(f"Executing {self.sdspackage}.{self.sdsmodule}.{self.sdspipeline}...")
        self.save_placeholder("abc", "deg")
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

    def execute(self):
        self.process.start()


def get_backtrace_info(error: BaseException) -> list[dict[str, typing.Any]]:
    backtrace_list = []
    for frame in stack_data.core.FrameInfo.stack_data(error.__traceback__):
        backtrace_list.append({"file": frame.filename, "line": str(frame.lineno)})
    return backtrace_list


def execute_pipeline(code: dict[str, dict[str, str]], sdspackage: str, sdsmodule: str, sdspipeline: str, exec_id: str):
    global multiprocessing_manager, global_messages_queue, global_placeholder_map
    if exec_id not in global_placeholder_map:
        global_placeholder_map[exec_id] = multiprocessing_manager.dict()
    process = PipelineProcess(code, sdspackage, sdsmodule, sdspipeline, exec_id, global_messages_queue,
                              global_placeholder_map[exec_id])
    process.execute()


def _get_placeholder_type(value: typing.Any):
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


def get_placeholder(exec_id: str, placeholder_name: str) -> (str | None, typing.Any):
    global global_placeholder_map
    if exec_id not in global_placeholder_map:
        return None, None
    if placeholder_name not in global_placeholder_map[exec_id]:
        return None, None
    value = global_placeholder_map[exec_id][placeholder_name]
    return _get_placeholder_type(value), value


def handle_queue_messages():
    global websocket_target
    while True:
        message = global_messages_queue.get()
        if websocket_target is not None:
            websocket_target.send(json.dumps(message))


def start_message_queue_handling():
    global messages_queue_thread
    messages_queue_thread = threading.Thread(target=handle_queue_messages, daemon=True)
    messages_queue_thread.start()


def set_new_websocket_target(ws):
    global websocket_target
    websocket_target = ws
