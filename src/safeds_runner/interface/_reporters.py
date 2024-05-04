from typing import Any

from safeds_runner.server._pipeline_manager import get_current_pipeline_process
from safeds_runner.server.messages._from_server import create_placeholder_value_message, create_progress_message
from safeds_runner.utils._get_type_name import get_type_name
from safeds_runner.utils._make_value_json_serializable import make_value_json_serializable


def report_placeholder_computed(placeholder_name: str) -> None:
    """
    Report that a placeholder has been computed.

    Parameters
    ----------
    placeholder_name:
        Name of the placeholder.
    """
    current_pipeline = get_current_pipeline_process()
    if current_pipeline is None:
        return  # pragma: no cover

    current_pipeline.send_message(
        create_progress_message(
            run_id=current_pipeline._payload.run_id,
            placeholder_name=placeholder_name,
            percentage=100,
        ),
    )


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
    current_pipeline = get_current_pipeline_process()
    if current_pipeline is None:
        return  # pragma: no cover

    # Also send a progress message
    current_pipeline.send_message(
        create_progress_message(
            run_id=current_pipeline._payload.run_id,
            placeholder_name=placeholder_name,
            percentage=100,
        ),
    )

    # Send the actual value
    requested_table_window = current_pipeline._payload.table_window
    serialized_value, chosen_window = make_value_json_serializable(value, requested_table_window)

    current_pipeline.send_message(
        create_placeholder_value_message(
            run_id=current_pipeline._payload.run_id,
            placeholder_name=placeholder_name,
            value=serialized_value,
            type_=get_type_name(value),
            window=chosen_window,
        ),
    )
