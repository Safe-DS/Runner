"""Module containing the main entry point, for starting the Safe-DS runner."""

from __future__ import annotations

import atexit
import logging
import os

from ._server import SafeDsServer


def start_server(port: int) -> None:
    """Start the Safe-DS Runner server."""
    # Allow prints to be unbuffered by default
    import builtins
    import functools

    builtins.print = functools.partial(print, flush=True)  # type: ignore[assignment]

    logging.getLogger().setLevel(logging.DEBUG)

    # Set PYTHONHASHSEED environment variable to a fixed value, to make hashes of builtin types more comparable between processes
    # Fixed values allow saving the cache to disk (in the future) and reusing it later
    os.environ["PYTHONHASHSEED"] = str(1396986624)

    safeds_server = SafeDsServer()
    safeds_server.startup(port)  # pragma: no cover
    atexit.register(lambda: safeds_server.shutdown)  # pragma: no cover
