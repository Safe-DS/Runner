"""Module containing the main entry point, for starting the Safe-DS runner."""

import logging

from safeds_runner.server.pipeline_manager import PipelineManager


def start_server(port: int) -> None:
    """Start the Safe-DS Runner server."""
    # Allow prints to be unbuffered by default
    import builtins
    import functools

    builtins.print = functools.partial(print, flush=True)  # type: ignore[assignment]

    logging.getLogger().setLevel(logging.DEBUG)
    # Startup early, so our multiprocessing setup works
    app_pipeline_manager = PipelineManager()
    app_pipeline_manager.startup()

    from safeds_runner.server.server import SafeDsServer

    safeds_server = SafeDsServer(app_pipeline_manager)  # pragma: no cover
    safeds_server.listen(port)  # pragma: no cover
