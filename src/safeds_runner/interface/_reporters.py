from typing import Any

from safeds_runner.server._pipeline_manager import current_pipeline


def report_placeholder_computed(placeholder_name: str) -> None:
    """
    Report that a placeholder has been computed.

    Parameters
    ----------
    placeholder_name:
        Name of the placeholder.
    """
    if current_pipeline is not None:
        current_pipeline.report_placeholder_computed(placeholder_name)


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
    if current_pipeline is not None:
        current_pipeline.report_placeholder_value(placeholder_name, value)
