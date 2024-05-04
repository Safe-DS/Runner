from typing import Any


def get_type_name(value: Any) -> str:
    """
    Get the name of the Python type for a given value.

    Parameters
    ----------
    value:
        Some object.s

    Returns
    -------
    type_name:
        Name of the Python type of the given value.
    """
    return type(value).__name__
