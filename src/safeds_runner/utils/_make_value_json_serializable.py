import base64
import json
import math
from typing import Any

from safeds.data.image.containers import Image
from safeds.data.labeled.containers import TabularDataset
from safeds.data.tabular.containers import Table

from safeds_runner.server.messages._from_server import Window as ChosenWindow
from safeds_runner.server.messages._to_server import Window as RequestedWindow


def make_value_json_serializable(value: Any, requested_table_window: RequestedWindow) -> tuple[Any, ChosenWindow | None]:
    """
    Convert a value to a JSON-serializable format.

    Parameters
    ----------
    value:
        The value to serialize.
    requested_table_window:
        Window to get for placeholders of type 'Table'.

    Returns
    -------
    serialized_value:
        The serialized value.
    chosen_window:
        The window of the value that was serialized.
    """
    if isinstance(value, Table):
        return make_table_json_serializable(value, requested_table_window)
    elif isinstance(value, TabularDataset):
        return make_table_json_serializable(value.to_table(), requested_table_window)
    elif isinstance(value, Image):
        return make_image_json_serializable(value)
    else:
        return make_other_json_serializable(value)


def make_table_json_serializable(
    table: Table,
    requested_window: RequestedWindow,
) -> tuple[Any, ChosenWindow | None]:
    # Compute sizes
    full_size = table.number_of_rows

    requested_size = requested_window.size if requested_window.size is not None else full_size
    requested_size = max(requested_size, 0)

    # Compute indices
    start_index = requested_window.start if requested_window.start is not None else 0
    start_index = max(start_index, 0)

    end_index = start_index + requested_size
    end_index = min(end_index, full_size)

    # Compute value
    slice_ = table.slice_rows(start=start_index, end=end_index)
    value = _replace_nan_and_infinity(slice_.to_dict())

    # Compute window
    if requested_window.start is not None or requested_window.size is not None:
        chosen_window = ChosenWindow(start=start_index, size=end_index - start_index, full_size=full_size)
    else:
        chosen_window = None

    return value, chosen_window


def _replace_nan_and_infinity(dict_: dict) -> dict:
    return {
        key: [
            value if not isinstance(value, float) or math.isfinite(value) else None
            for value in dict_[key]
        ]
        for key in dict_
    }


def make_image_json_serializable(image: Image) -> tuple[Any, ChosenWindow | None]:
    dict_ = {
        "format": "png",
        "bytes": str(base64.encodebytes(image._repr_png_()), "utf-8"),
    }
    return dict_, None


def make_other_json_serializable(value: Any) -> tuple[Any, ChosenWindow | None]:
    try:
        json.dumps(value)
    except TypeError:
        return "<Not displayable>", None
    else:
        return value, None
