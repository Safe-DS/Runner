"""Module that contains the memoization logic."""

import functools
import logging
import operator
import time
from collections.abc import Callable
from typing import Any

import psutil

from safeds_runner.memoization._memoization_stats import MemoizationStats
from safeds_runner.memoization._memoization_strategies import STAT_ORDER_PRIORITY
from safeds_runner.memoization._memoization_utils import (
    MemoizationKey,
    _create_memoization_key,
    _get_size_of_value,
    _unwrap_value_from_shared_memory,
    _wrap_value_to_shared_memory,
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
        map_values:
            Value store dictionary
        map_stats:
            Stats dictionary
        """
        self._map_values: dict[MemoizationKey, Any] = map_values
        self._map_stats: dict[str, MemoizationStats] = map_stats
        # Set to half of physical available memory as a guess, in the future this could be set with an option
        self.max_size: int | None = psutil.virtual_memory().total // 2
        self.value_removal_strategy = STAT_ORDER_PRIORITY

    def get_cache_size(self) -> int:
        """
        Calculate the current size of the memoization cache.

        Returns
        -------
        cache_size:
            Amount of bytes, this cache occupies. This may be an estimate.
        """
        return functools.reduce(
            operator.add,
            [functools.reduce(operator.add, stats.memory_sizes, 0) for stats in self._map_stats.values()],
            0,
        )

    def ensure_capacity(self, needed_capacity: int) -> None:
        """
        Ensure that the requested capacity is at least available, by freeing values from the cache.

        If the needed capacity is larger than the max capacity, this function will not do anything to ensure further operation.

        Parameters
        ----------
        needed_capacity:
            Amount of free storage space requested, in bytes
        """
        if self.max_size is None:
            return
        free_size = self.max_size - self.get_cache_size()
        while free_size < needed_capacity < self.max_size:
            self.remove_worst_element(needed_capacity - free_size)
            free_size = self.max_size - self.get_cache_size()

    def remove_worst_element(self, capacity_to_free: int) -> None:
        """
        Remove the worst elements (most useless) from the cache, to free at least the provided amount of bytes.

        Parameters
        ----------
        capacity_to_free:
            Amount of bytes that should be additionally freed, after this function returns
        """
        copied_stats = list(self._map_stats.copy().items())
        # Sort functions to remove them from the cache in a specific order
        copied_stats.sort(key=self.value_removal_strategy)
        # Calculate which functions should be removed from the cache
        bytes_freed = 0
        functions_to_free = []
        for function, stats in copied_stats:
            if bytes_freed >= capacity_to_free:
                break
            function_sum_bytes = functools.reduce(operator.add, stats.memory_sizes, 0)
            bytes_freed += function_sum_bytes
            functions_to_free.append(function)
        # Remove references to values, and let the gc handle the actual objects
        for key in list(self._map_values.keys()):
            for function_to_free in functions_to_free:
                if key[0] == function_to_free:
                    del self._map_values[key]
        # Remove stats, as content is gone
        for function_to_free in functions_to_free:
            del self._map_stats[function_to_free]

    def memoized_function_call(
        self,
        fully_qualified_function_name: str,
        callable_: Callable,
        positional_arguments: list[Any],
        keyword_arguments: dict[str, Any],
        hidden_arguments: list[Any],
    ) -> Any:
        """
        Handle a memoized function call.

        Looks up the stored value, determined by function name, parameters and hidden parameters and returns it if found.
        If no value is found, computes the value using the provided callable and stores it in the map.
        Every call to this function will update the memoization stats.

        Parameters
        ----------
        fully_qualified_function_name:
            Fully qualified function name
        callable_:
            Function that is called and memoized if the result was not found in the memoization map
        positional_arguments:
            List of arguments passed to the function
        keyword_arguments:
            Dictionary of keyword arguments passed to the function
        hidden_arguments:
            List of hidden arguments for the function. This is used for memoizing some impure functions.

        Returns
        -------
        result:
            The result of the specified function, if any exists
        """
        access_timestamp = time.time_ns()

        # Lookup memoized value
        lookup_time_start = time.perf_counter_ns()
        key = _create_memoization_key(
            fully_qualified_function_name,
            positional_arguments,
            keyword_arguments,
            hidden_arguments,
        )
        try:
            memoized_value = self._lookup_value(key)
        # Pickling may raise AttributeError, hashing may raise TypeError
        except (AttributeError, TypeError) as exception:
            # Fallback to executing the call to continue working, but inform user about this failure
            logging.exception(
                "Could not lookup value for function %s. Falling back to calling the function",
                fully_qualified_function_name,
                exc_info=exception,
            )
            return callable_(*positional_arguments, **keyword_arguments)
        lookup_time = time.perf_counter_ns() - lookup_time_start

        # Hit
        if memoized_value is not None:
            self._update_stats_on_hit(fully_qualified_function_name, access_timestamp, lookup_time)
            return memoized_value

        # Miss
        computation_time_start = time.perf_counter_ns()
        computed_value = callable_(*positional_arguments, **keyword_arguments)
        computation_time = time.perf_counter_ns() - computation_time_start
        memory_size = _get_size_of_value(computed_value)

        memoizable_value = _wrap_value_to_shared_memory(computed_value)
        if self.max_size is not None:
            self.ensure_capacity(_get_size_of_value(memoized_value))

        try:
            self._map_values[key] = memoizable_value
        # Pickling may raise AttributeError in combination with multiprocessing
        except AttributeError as exception:
            # Fallback to returning computed value, but inform user about this failure
            logging.exception(
                "Could not store value for function %s.",
                fully_qualified_function_name,
                exc_info=exception,
            )
            return computed_value

        self._update_stats_on_miss(
            fully_qualified_function_name,
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

    def _lookup_value(self, key: MemoizationKey) -> Any | None:
        """
        Lookup a potentially existing value from the memoization cache.

        Parameters
        ----------
        key:
            Memoization Key

        Returns
        -------
        value:
            The value corresponding to the provided memoization key, if any exists.
        """
        looked_up_value = self._map_values.get(key)
        return _unwrap_value_from_shared_memory(looked_up_value)

    def _update_stats_on_hit(self, function_name: str, access_timestamp: int, lookup_time: int) -> None:
        """
        Update the memoization stats on a cache hit.

        Parameters
        ----------
        function_name:
            Fully qualified function name
        access_timestamp:
            Timestamp when this value was last accessed
        lookup_time:
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
        function_name:
            Fully qualified function name
        access_timestamp:
            Timestamp when this value was last accessed
        lookup_time:
            Duration the comparison took in nanoseconds
        computation_time:
            Duration the computation of the new value took in nanoseconds
        memory_size:
            Memory the newly computed value takes up in bytes
        """
        stats = self._map_stats.get(function_name)
        if stats is None:
            stats = MemoizationStats()

        stats.update_on_miss(access_timestamp, lookup_time, computation_time, memory_size)
        self._map_stats[function_name] = stats
