from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class MemoizationStats:
    last_access: int
    computation_time: int
    lookup_time: int
    memory_size: int


class MemoizationMap:
    def __init__(self, map_values: dict[tuple[str, tuple[Any], tuple[Any]], Any],
                 map_stats: dict[tuple[str, tuple[Any], tuple[Any]], MemoizationStats]):
        self.map_values: dict[tuple[str, tuple[Any], tuple[Any]], Any] = map_values
        self.map_stats: dict[tuple[str, tuple[Any], tuple[Any]], MemoizationStats] = map_stats

    def memoized_function_call(self, function_name: str, function_callable: Callable, parameters: list[Any],
                               hidden_parameters: list[Any]) -> Any:
        key = (function_name, _convert_list_to_tuple(parameters), _convert_list_to_tuple(hidden_parameters))
        if key in self.map_values:
            return self.map_values[key]
        result = function_callable(*parameters)
        self.map_values[key] = result
        return result


def _convert_list_to_tuple(values: list) -> tuple:
    """
    Recursively convert a mutable list of values to an immutable tuple containing the same values, to make the values hashable.

    Parameters
    ----------
    values : list
        Values that should be converted to a tuple

    Returns
    -------
    tuple
        Converted list containing all the elements of the provided list
    """
    return tuple(_convert_list_to_tuple(value) if isinstance(value, list) else value for value in values)
