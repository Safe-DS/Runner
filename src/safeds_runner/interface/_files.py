from __future__ import annotations

import typing
from pathlib import Path


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
        Names of the files.

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
