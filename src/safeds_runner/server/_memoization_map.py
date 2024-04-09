"""Module that contains the memoization logic."""

import functools
import operator
import logging
import time
from collections.abc import Callable
from typing import Any

from safeds_runner.server._memoization_stats import MemoizationStats
from safeds_runner.server._memoization_strategies import STAT_ORDER_PRIORITY
from safeds_runner.server._memoization_utils import MemoizationKey, _get_size_of_value, ExplicitIdentityWrapper, ExplicitIdentityWrapperLazy, _create_memoization_key, _convert_value_to_memoizable_format


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
        self.max_size = None
        self.value_removal_strategy = STAT_ORDER_PRIORITY

    def get_cache_size(self) -> int:
        """
        Calculate the current size of the memoization cache.

        Returns
        -------
        Amount of bytes, this cache occupies. This may be an estimate.
        """
        return functools.reduce(operator.add, [_get_size_of_value(value) for value in self._map_values.values()], 0)

    def ensure_capacity(self, needed_capacity: int) -> None:
        """
        Ensure that the requested capacity is at least available, by freeing values from the cache.
        If the needed capacity is larger than the max capacity, this function will not do anything to ensure further operation.

        Parameters
        ----------
        needed_capacity
            Amount of free storage space requested, in bytes
        """
        free_size = self.max_size - self.get_cache_size()
        while free_size < needed_capacity < self.max_size:
            self.remove_worst_element(needed_capacity - free_size)
            free_size = self.max_size - self.get_cache_size()

    def remove_worst_element(self, capacity_to_free: int) -> None:
        """
        Remove the worst elements (most useless) from the cache, to free at least the provided amount of bytes.

        Parameters
        ----------
        capacity_to_free
            Amount of bytes that should be additionally freed, after this function returns
        """
        copied_stats = [(function, stats) for function, stats in self._map_stats.copy().items()]
        # Sort functions to remove them from the cache in a specific order
        copied_stats.sort(key=self.value_removal_strategy[0], reverse=self.value_removal_strategy[1])
        # Calculate which functions should be removed from the cache
        bytes_freed = 0
        functions_to_free = []
        for (function, stats) in copied_stats:
            if bytes_freed >= capacity_to_free:
                break
            function_sum_bytes = functools.reduce(operator.add, stats.memory_sizes, 0)
            bytes_freed += function_sum_bytes
            functions_to_free.append(function)
        # Remove references to values, and let the gc handle the actual objects
        for key in self._map_values.keys():
            for function_to_free in functions_to_free:
                if key[0] == function_to_free:
                    del self._map_values[key]
        # Remove stats, as content is gone
        for function_to_free in functions_to_free:
            del self._map_stats[function_to_free]

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
        key = _create_memoization_key(function_name, parameters, hidden_parameters)
        try:
            memoized_value = self._lookup_value(key)
        # Pickling may raise AttributeError, hashing may raise TypeError
        except (AttributeError, TypeError):
            return function_callable(*parameters)
        lookup_time = time.perf_counter_ns() - lookup_time_start

        # Hit
        if memoized_value is not None:
            self._update_stats_on_hit(function_name, access_timestamp, lookup_time)
            if isinstance(memoized_value, ExplicitIdentityWrapper):
                return memoized_value.value
            elif isinstance(memoized_value, ExplicitIdentityWrapperLazy):
                memoized_value._unpackvalue()
                return memoized_value.value
            else:
                return memoized_value

        # Miss
        computation_time_start = time.perf_counter_ns()
        computed_value = function_callable(*parameters)
        computation_time = time.perf_counter_ns() - computation_time_start
        memory_size = _get_size_of_value(computed_value)

        memoizable_value = _convert_value_to_memoizable_format(computed_value)
        if self.max_size is not None:
            self.ensure_capacity(_get_size_of_value(memoized_value))
        self._map_values[key] = memoizable_value

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

        if isinstance(computed_value, ExplicitIdentityWrapper):
            return computed_value.value
        else:
            return computed_value

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
        looked_up_value = self._map_values.get(key)
        if isinstance(looked_up_value, tuple):
            results = []
            for entry in looked_up_value:
                if isinstance(entry, ExplicitIdentityWrapperLazy):
                    entry._unpackvalue()
                    results.append(entry.value)
            return tuple(results)
        if isinstance(looked_up_value, ExplicitIdentityWrapperLazy):
            looked_up_value._unpackvalue()
            return looked_up_value.value
        if isinstance(looked_up_value, ExplicitIdentityWrapper):
            return looked_up_value.value
        return looked_up_value

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
