"""Module containing the main entry point, for starting the Safe-DS runner."""

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
    safeds_server.listen(port)  # pragma: no cover
