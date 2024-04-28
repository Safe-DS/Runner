"""Module that contains the infrastructure for finding and loading modules in-memory."""

from __future__ import annotations

import importlib.abc
import importlib.util
import logging
import sys
import typing
from abc import ABC

if typing.TYPE_CHECKING:
    import types
    from importlib.machinery import ModuleSpec


class InMemoryLoader(importlib.abc.SourceLoader, ABC):
    """Load a virtual python module from a byte array and a filename."""

    def __init__(self, code_bytes: bytes, filename: str):
        """
        Create a new in-memory loader.

        Parameters
        ----------
        code_bytes:
            Byte array containing python code.
        filename:
            Filename of the python module.
        """
        self.code_bytes = code_bytes
        self.filename = filename

    def get_data(self, _path: bytes | str) -> bytes:
        """
        Get module code as a byte array.

        Parameters
        ----------
        _path:
            Module path.

        Returns
        -------
        code_as_bytes:
            Module code.
        """
        return self.code_bytes

    def get_filename(self, _fullname: str) -> str:
        """
        Get file name for a module path.

        Parameters
        ----------
        _fullname:
            Module path.

        Returns
        -------
        filename:
            virtual module path, as located in the code array in the InMemoryFinder that created this loader.
        """
        return self.filename


class InMemoryFinder(importlib.abc.MetaPathFinder):
    """Find python modules in an in-memory dictionary."""

    def __init__(self, code: dict[str, dict[str, str]]):
        """
        Create a new in-memory finder.

        Parameters
        ----------
        code:
            A dictionary containing the code to be executed,
            grouped by module path containing a mapping from module name to module code.
        """
        self.code = code
        self.allowed_packages = set(code.keys())
        self.imports_to_remove: set[str] = set()
        for key in code:
            self._add_possible_packages_for_package_path(key)

    def _add_possible_packages_for_package_path(self, package_path: str) -> None:
        while "." in package_path:
            package_path = package_path.rpartition(".")[0]
            self.allowed_packages.add(package_path)

    def find_spec(
        self,
        fullname: str,
        path: typing.Sequence[str] | None = None,
        target: types.ModuleType | None = None,
    ) -> ModuleSpec | None:
        """
        Find a module which may be registered in the code dictionary.

        Parameters
        ----------
        fullname:
            Full module path (separated with '.').
        path:
            Module Path.
        target:
            Module Type.

        Returns
        -------
        module_spec:
            A module spec, if found. None otherwise
        """
        logging.debug("Find Spec: %s %s %s", fullname, path, target)
        if fullname in self.allowed_packages:
            parent_package = importlib.util.spec_from_loader(
                fullname,
                loader=InMemoryLoader(b"", fullname.replace(".", "/")),
            )
            if parent_package is None:
                return None  # pragma: no cover
            if parent_package.submodule_search_locations is None:
                parent_package.submodule_search_locations = []
            parent_package.submodule_search_locations.append(fullname.replace(".", "/"))
            self.imports_to_remove.add(fullname)
            return parent_package
        module_path = fullname.split(".")
        if len(module_path) == 1 and "" in self.code and fullname in self.code[""]:
            self.imports_to_remove.add(fullname)
            return importlib.util.spec_from_loader(
                fullname,
                loader=InMemoryLoader(self.code[""][fullname].encode("utf-8"), fullname.replace(".", "/")),
                origin="",
            )
        parent_package_path = ".".join(module_path[:-1])
        submodule_name = module_path[-1]
        if parent_package_path in self.code and submodule_name in self.code[parent_package_path]:
            self.imports_to_remove.add(fullname)
            return importlib.util.spec_from_loader(
                fullname,
                loader=InMemoryLoader(
                    self.code[parent_package_path][submodule_name].encode("utf-8"),
                    fullname.replace(".", "/"),
                ),
                origin=parent_package_path,
            )
        return None  # pragma: no cover

    def attach(self) -> None:
        """Attach this finder to the meta path."""
        sys.meta_path.append(self)

    def detach(self) -> None:
        """Remove modules found in this finder and remove finder from meta path."""
        # As modules should not be used from other modules, outside our pipeline,
        # it should be safe to just remove all newly imported modules
        for key in self.imports_to_remove:
            if key in sys.modules:
                del sys.modules[key]
        sys.meta_path.remove(self)
