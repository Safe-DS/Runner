from typing import Any


def get_safeds_type(value: Any) -> str:
    """
    Get the Safe-DS type for a given Python object.

    Parameters
    ----------
    value:
        A Python object.

    Returns
    -------
    safeds_type:
        Safe-DS type of the given object.
    """
    match value:
        case bool():
            return "Boolean"
        case float():
            return "Float"
        case int():
            return "Int"
        case str():
            return "String"
        case object():
            object_name = type(value).__name__
            match object_name:
                case "function":
                    return "Callable"
                case "NoneType":
                    return "Nothing?"
                case _:
                    return object_name
        case _:  # pragma: no cover
            return "Any?"  # pragma: no cover
