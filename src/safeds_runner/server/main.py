"""Module containing the main entry point, for starting the Safe-DS runner."""

import logging

from ._server import SafeDsServer


def start_server(port: int) -> None:
    """Start the Safe-DS Runner server."""
    # Allow prints to be unbuffered by default
    import builtins
    import functools

    builtins.print = functools.partial(print, flush=True)  # type: ignore[assignment]

    logging.getLogger().setLevel(logging.DEBUG)

    safeds_server = SafeDsServer()
    safeds_server.listen(port)  # pragma: no cover
