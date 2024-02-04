"""Module that contains the memoization logic and stats."""
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable

from safeds.data.image.containers import Image
from safeds.data.tabular.containers import Table, Column, Row, TaggedTable, TimeSeries
from safeds.data.tabular.typing import Schema


@dataclass(frozen=True)
class MemoizationStats:
    """
    Statistics calculated for every memoization call.

    Parameters
    ----------
    last_access
        Absolute timestamp since the unix epoch of the last access to the memoized value in nanoseconds
    computation_time
        Duration the computation of the value took in nanoseconds
    lookup_time
        Duration the lookup of the value took in nanoseconds (key comparison + IPC)
    memory_size
        Amount of memory the memoized value takes up in bytes
    """
    last_access: int
    computation_time: int
    lookup_time: int
    memory_size: int

    def __str__(self):
        return f"Last access: {self.last_access}, computation time: {self.computation_time}, lookup time: {self.lookup_time}, memory size: {self.memory_size}"


class MemoizationMap:
    """
    The memoization map handles memoized function calls, looks up stored values, computes new values if needed and calculates and updates statistics.
    """
    def __init__(self, map_values: dict[tuple[str, tuple[Any], tuple[Any]], Any],
                 map_stats: dict[tuple[str, tuple[Any], tuple[Any]], MemoizationStats]):
        """
        Create a new memoization map using a value store dictionary and a stats dictionary.

        Parameters
        ----------
        map_values
            Value store dictionary
        map_stats
            Stats dictionary
        """
        self.map_values: dict[tuple[str, tuple[Any], tuple[Any]], Any] = map_values
        self.map_stats: dict[tuple[str, tuple[Any], tuple[Any]], MemoizationStats] = map_stats

    def memoized_function_call(self, function_name: str, function_callable: Callable, parameters: list[Any],
                               hidden_parameters: list[Any]) -> Any:
        """
        Handles a memoized function call.

        Looks up the stored value, determined by function name, parameters and hidden parameters and returns it if found.
        If no value is found, computes the value using the provided callable and stores it in the map.
        Every call to this function will update the memoization stats.

        Parameters
        ----------
        function_name
            Fully qualified function name
        function_callable
            Function that is called and memoized if the result was not found in the memoization map
        parameters
            List of parameters passed to the function
        hidden_parameters
            List of hidden parameters for the function. This is used for memoizing some impure functions.

        Returns
        -------
        The result of the specified function, if any exists
        """
        key = (function_name, _convert_list_to_tuple(parameters), _convert_list_to_tuple(hidden_parameters))
        time_compare_start = time.perf_counter_ns()
        try:
            potential_value = self.map_values[key]
            time_compare_end = time.perf_counter_ns()
            # Use time_ns for absolute time points, as perf_counter_ns does not guarantee any fixed reference-point
            time_last_access = time.time_ns()
            time_compare = time_compare_end - time_compare_start
            old_memoization_stats = self.map_stats[key]
            memoization_stats = MemoizationStats(time_last_access, old_memoization_stats.computation_time,
                                                 time_compare, old_memoization_stats.memory_size)
            self.map_stats[key] = memoization_stats
            print(f"Updated memoization stats for {function_name}: {memoization_stats}")
            return potential_value
        except KeyError:
            time_compare_end = time.perf_counter_ns()
            time_compare = time_compare_end - time_compare_start
        time_compute_start = time.perf_counter_ns()
        result = function_callable(*parameters)
        time_compute_end = time.perf_counter_ns()
        # Use time_ns for absolute time points, as perf_counter_ns does not guarantee any fixed reference-point
        time_last_access = time.time_ns()
        time_compute = time_compute_end - time_compute_start
        value_memory = _get_size_of_value(result)
        self.map_values[key] = result
        memoization_stats = MemoizationStats(time_last_access, time_compute, time_compare, value_memory)
        print(f"New memoization stats for {function_name}: {memoization_stats}")
        self.map_stats[key] = memoization_stats
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


def _get_size_of_value(value: Any) -> int:
    """
    Recursively calculate the memory usage of a given value.

    Parameters
    ----------
    value
        Any value of which the memory usage should be calculated.

    Returns
    -------
    Size of the provided value in bytes
    """
    size_immediate = sys.getsizeof(value)
    if isinstance(value, dict):
        return sum(map(_get_size_of_value, value.items())) + size_immediate
    elif isinstance(value, list) or isinstance(value, tuple) or isinstance(value, set) or isinstance(value, frozenset):
        return sum(map(_get_size_of_value, value)) + size_immediate
    elif isinstance(value, Table):
        return _get_size_of_value(value._data) + _get_size_of_value(value._schema) + size_immediate
    elif isinstance(value, Schema):
        return _get_size_of_value(value._schema) + size_immediate
    elif isinstance(value, Image):
        return _get_size_of_value(value._image_tensor) + value._image_tensor.element_size() * value._image_tensor.nelement() + size_immediate
    elif isinstance(value, Column):
        return _get_size_of_value(value._data) + _get_size_of_value(value._name) + _get_size_of_value(value._type) + size_immediate
    elif isinstance(value, Row):
        return _get_size_of_value(value._data) + _get_size_of_value(value._schema) + size_immediate
    elif isinstance(value, TaggedTable):
        return _get_size_of_value(value._data) + _get_size_of_value(value._schema) + _get_size_of_value(
            value._features) + _get_size_of_value(value._target) + size_immediate
    elif isinstance(value, TimeSeries):
        return _get_size_of_value(value._data) + _get_size_of_value(value._schema) + _get_size_of_value(value._time) + _get_size_of_value(value._features) + _get_size_of_value(value._target) + size_immediate
    else:
        return size_immediate
