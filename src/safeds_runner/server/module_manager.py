import importlib.abc
import typing
from abc import ABC
from importlib.machinery import ModuleSpec
import sys
import importlib.util
import types
import runpy
import logging

import stack_data


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


def _execute_pipeline(code: dict[str, dict[str, str]], sdspackage: str, sdsmodule: str, sdspipeline: str):
    pipeline_finder = InMemoryFinder(code)
    pipeline_finder.attach()
    main_module = f"gen_{sdsmodule}_{sdspipeline}"
    try:
        runpy.run_module(main_module, run_name="__main__")  # TODO Is the Safe-DS-Package relevant here?
    except BaseException:
        raise  # This should keep the backtrace
    finally:
        pipeline_finder.detach()


def execute_pipeline(code: dict[str, dict[str, str]], sdspackage: str, sdsmodule: str, sdspipeline: str,
                     context_globals: dict):
    logging.info(f"Executing {sdspackage}.{sdsmodule}.{sdspipeline}...")
    exec('_execute_pipeline(code, sdspackage, sdsmodule, sdspipeline)', context_globals,
         {"code": code, "sdspackage": sdspackage, "sdsmodule": sdsmodule, "sdspipeline": sdspipeline,
          "_execute_pipeline": _execute_pipeline, "runpy": runpy})
