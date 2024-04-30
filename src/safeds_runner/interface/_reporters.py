from typing import Any

from safeds_runner.server import _pipeline_manager


def report_placeholder_computed(placeholder_name: str) -> None:
    """
    Report that a placeholder has been computed.

    Parameters
    ----------
    placeholder_name:
        Name of the placeholder.
    """
    if _pipeline_manager.current_pipeline is not None:
        _pipeline_manager.current_pipeline.report_placeholder_computed(placeholder_name)


def report_placeholder_value(placeholder_name: str, value: Any) -> None:
    """
    Report the value of a placeholder.

    Parameters
    ----------
    placeholder_name:
        Name of the placeholder.
    value:
        Value of the placeholder.
    """
    if _pipeline_manager.current_pipeline is not None:
        _pipeline_manager.current_pipeline.report_placeholder_value(placeholder_name, value)
