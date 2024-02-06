"""Module that contains the memoization logic and stats."""

import dataclasses
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeAlias

MemoizationKey: TypeAlias = tuple[str, tuple[Any], tuple[Any]]


@dataclass(frozen=True)
class MemoizationStats:
    """
    Statistics calculated for every memoization call.

    Parameters
    ----------
    access_timestamps
        Absolute timestamp since the unix epoch of the last access to the memoized value in nanoseconds
    lookup_times
        Duration the lookup of the value took in nanoseconds (key comparison + IPC)
    computation_times
        Duration the computation of the value took in nanoseconds
    memory_sizes
        Amount of memory the memoized value takes up in bytes
    """

    access_timestamps: list[int] = dataclasses.field(default_factory=list)
    lookup_times: list[int] = dataclasses.field(default_factory=list)
    computation_times: list[int] = dataclasses.field(default_factory=list)
    memory_sizes: list[int] = dataclasses.field(default_factory=list)

    def __str__(self) -> str:
        """
        Summarizes stats contained in this object.

        Returns
        -------
        Summary of stats
        """
        return (  # pragma: no cover
            f"Last access: {self.access_timestamps}, computation time: {self.computation_times}, lookup time:"
            f" {self.lookup_times}, memory size: {self.memory_sizes}"
        )


def _create_memoization_key(function_name: str, parameters: list[Any], hidden_parameters: list[Any]) -> MemoizationKey:
    """
    Convert values provided to a memoized function call to a memoization key.

    Parameters
    ----------
    function_name
        Fully qualified function name
    parameters
        List of parameters passed to the function
    hidden_parameters
        List of parameters not passed to the function

    Returns
    -------
    A memoization key, which contains the lists converted to tuples
    """
    return function_name, _convert_list_to_tuple(parameters), _convert_list_to_tuple(hidden_parameters)


class MemoizationMap:
    """
    The memoization map handles memoized function calls.

    This contains looking up stored values, computing new values if needed and calculating and updating statistics.
    """

    def __init__(
        self,
        map_values: dict[MemoizationKey, Any],
        map_stats: dict[str, MemoizationStats],
    ):
        """
        Create a new memoization map using a value store dictionary and a stats dictionary.

        Parameters
        ----------
        map_values
            Value store dictionary
        map_stats
            Stats dictionary
        """
        self._map_values: dict[MemoizationKey, Any] = map_values
        self._map_stats: dict[str, MemoizationStats] = map_stats

    def memoized_function_call(
        self,
        function_name: str,
        function_callable: Callable,
        parameters: list[Any],
        hidden_parameters: list[Any],
    ) -> Any:
        """
        Handle a memoized function call.

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
        time_compare_start = time.perf_counter_ns()
        key = _create_memoization_key(function_name, parameters, hidden_parameters)
        potential_value = self._lookup_value(key, time_compare_start)
        if potential_value is not None:
            return potential_value
        return self._memoize_new_value(key, function_callable, time_compare_start)

    def _lookup_value(self, key: MemoizationKey, time_compare_start: int) -> Any | None:
        """
        Lookup a potentially existing value from the memoization cache.

        Parameters
        ----------
        key
            Memoization Key
        time_compare_start
            Point in time where the comparison time started

        Returns
        -------
        The value corresponding to the provided memoization key, if any exists.
        """
        try:
            potential_value = self._map_values[key]
        except KeyError:
            return None
        else:
            time_compare_end = time.perf_counter_ns()
            # Use time_ns for absolute time points, as perf_counter_ns does not guarantee any fixed reference-point
            time_last_access = time.time_ns()
            time_compare = time_compare_end - time_compare_start
            self._update_stats_on_hit(key[0], time_last_access, time_compare)
            logging.info(
                "Updated memoization stats for %s: (last_access=%s, time_compare=%s)",
                key[0],
                time_last_access,
                time_compare,
            )
            return potential_value

    def _memoize_new_value(self, key: MemoizationKey, function_callable: Callable, time_compare_start: int) -> Any:
        """
        Memoize a new function call and return computed the result.

        Parameters
        ----------
        key
            Memoization Key
        function_callable
            Function that will be called
        time_compare_start
            Point in time where the comparison time started

        Returns
        -------
        The newly computed value corresponding to the provided memoization key
        """
        time_compare_end = time.perf_counter_ns()
        time_compare = time_compare_end - time_compare_start
        time_compute_start = time.perf_counter_ns()
        result = function_callable(*key[1])
        time_compute_end = time.perf_counter_ns()
        # Use time_ns for absolute time points, as perf_counter_ns does not guarantee any fixed reference-point
        time_last_access = time.time_ns()
        time_compute = time_compute_end - time_compute_start
        value_memory = _get_size_of_value(result)
        self._map_values[key] = result
        self._update_stats_on_miss(key[0], time_last_access, time_compare, time_compute, value_memory)
        logging.info(
            "New memoization stats for %s: (last_access=%s, time_compare=%s, time_compute=%s, memory=%s)",
            key[0],
            time_last_access,
            time_compare,
            time_compute,
            value_memory,
        )
        return result

    def _update_stats_on_hit(self, function_name: str, last_access: int, time_compare: int) -> None:
        """
        Update the memoization stats on a cache hit.

        Parameters
        ----------
        function_name
            Fully qualified function name
        last_access
            Timestamp where this value was last accessed
        time_compare
            Duration the comparison took
        """
        old_memoization_stats = self._map_stats[function_name]
        old_memoization_stats.access_timestamps.append(last_access)
        old_memoization_stats.lookup_times.append(time_compare)
        self._map_stats[function_name] = old_memoization_stats

    def _update_stats_on_miss(
        self,
        function_name: str,
        last_access: int,
        time_compare: int,
        time_computation: int,
        memory_size: int,
    ) -> None:
        """
        Update the memoization stats on a cache miss.

        Parameters
        ----------
        function_name
            Fully qualified function name
        last_access
            Timestamp where this value was last accessed
        time_compare
            Duration the comparison took
        time_computation
            Duration the computation of the new value took
        memory_size
            Memory the newly computed value takes up
        """
        old_memoization_stats = self._map_stats.get(function_name)
        if old_memoization_stats is None:
            old_memoization_stats = MemoizationStats()
        old_memoization_stats.access_timestamps.append(last_access)
        old_memoization_stats.lookup_times.append(time_compare)
        old_memoization_stats.computation_times.append(time_computation)
        old_memoization_stats.memory_sizes.append(memory_size)
        self._map_stats[function_name] = old_memoization_stats


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
        return (
            sum(map(_get_size_of_value, value.keys())) + sum(map(_get_size_of_value, value.values())) + size_immediate
        )
    elif isinstance(value, frozenset | list | set | tuple):
        return sum(map(_get_size_of_value, value)) + size_immediate
    else:
        return size_immediate
