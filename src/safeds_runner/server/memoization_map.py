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

    def update_on_hit(self, access_timestamp: int, lookup_time: int) -> None:
        """
        Update the memoization stats on a cache hit.

        Parameters
        ----------
        access_timestamp
            Timestamp when this value was last accessed
        lookup_time
            Duration the comparison took in nanoseconds
        """
        self.access_timestamps.append(access_timestamp)
        self.lookup_times.append(lookup_time)

    def update_on_miss(self, access_timestamp: int, lookup_time: int, computation_time: int, memory_size: int) -> None:
        """
        Update the memoization stats on a cache miss.

        Parameters
        ----------
        access_timestamp
            Timestamp when this value was last accessed
        lookup_time
            Duration the comparison took in nanoseconds
        computation_time
            Duration the computation of the new value took in nanoseconds
        memory_size
            Memory the newly computed value takes up in bytes
        """
        self.access_timestamps.append(access_timestamp)
        self.lookup_times.append(lookup_time)
        self.computation_times.append(computation_time)
        self.memory_sizes.append(memory_size)

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
        access_timestamp = time.time_ns()

        # Lookup memoized value
        lookup_time_start = time.perf_counter_ns()
        key = self._create_memoization_key(function_name, parameters, hidden_parameters)
        memoized_value = self._lookup_value(key)
        lookup_time = time.perf_counter_ns() - lookup_time_start

        # Hit
        if memoized_value is not None:
            self._update_stats_on_hit(function_name, access_timestamp, lookup_time)
            return memoized_value

        # Miss
        computation_time_start = time.perf_counter_ns()
        computed_value = self._compute_and_memoize_value(key, function_callable, parameters)
        computation_time = time.perf_counter_ns() - computation_time_start
        memory_size = _get_size_of_value(computed_value)

        self._update_stats_on_miss(
            function_name,
            access_timestamp,
            lookup_time,
            computation_time,
            memory_size,
        )

        logging.info(
            "New memoization stats for %s: (access_timestamp=%s, lookup_time=%s, computation_time=%s, memory_size=%s)",
            key[0],
            access_timestamp,
            lookup_time,
            computation_time,
            memory_size,
        )

        return computed_value

    def _create_memoization_key(
        self,
        function_name: str,
        parameters: list[Any],
        hidden_parameters: list[Any],
    ) -> MemoizationKey:
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

    def _lookup_value(self, key: MemoizationKey) -> Any | None:
        """
        Lookup a potentially existing value from the memoization cache.

        Parameters
        ----------
        key
            Memoization Key

        Returns
        -------
        The value corresponding to the provided memoization key, if any exists.
        """
        return self._map_values.get(key)

    def _compute_and_memoize_value(
        self,
        key: MemoizationKey,
        function_callable: Callable,
        parameters: list[Any],
    ) -> Any:
        """
        Memoize a new function call and return computed the result.

        Parameters
        ----------
        key
            Memoization Key
        function_callable
            Function that will be called
        parameters
            List of parameters passed to the function

        Returns
        -------
        The newly computed value corresponding to the provided memoization key
        """
        result = function_callable(*parameters)
        self._map_values[key] = result
        return result

    def _update_stats_on_hit(self, function_name: str, access_timestamp: int, lookup_time: int) -> None:
        """
        Update the memoization stats on a cache hit.

        Parameters
        ----------
        function_name
            Fully qualified function name
        access_timestamp
            Timestamp when this value was last accessed
        lookup_time
            Duration the comparison took in nanoseconds
        """
        stats = self._map_stats[function_name]
        stats.update_on_hit(access_timestamp, lookup_time)

        # This assignment is required for multiprocessing, see
        # https://docs.python.org/3.11/library/multiprocessing.html#proxy-objects
        self._map_stats[function_name] = stats

    def _update_stats_on_miss(
        self,
        function_name: str,
        access_timestamp: int,
        lookup_time: int,
        computation_time: int,
        memory_size: int,
    ) -> None:
        """
        Update the memoization stats on a cache miss.

        Parameters
        ----------
        function_name
            Fully qualified function name
        access_timestamp
            Timestamp when this value was last accessed
        lookup_time
            Duration the comparison took in nanoseconds
        computation_time
            Duration the computation of the new value took in nanoseconds
        memory_size
            Memory the newly computed value takes up in bytes
        """
        stats = self._map_stats.get(function_name)
        if stats is None:
            stats = MemoizationStats()

        stats.update_on_miss(access_timestamp, lookup_time, computation_time, memory_size)
        self._map_stats[function_name] = stats


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
