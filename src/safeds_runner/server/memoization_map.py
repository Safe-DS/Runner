import sys
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class MemoizationStats:
    last_access: int
    computation_time: int
    lookup_time: int
    memory_size: int

    def __str__(self):
        return f"Last access: {self.last_access}, computation time: {self.computation_time}, lookup time: {self.lookup_time}, memory size: {self.memory_size}"


class MemoizationMap:
    def __init__(self, map_values: dict[tuple[str, tuple[Any], tuple[Any]], Any],
                 map_stats: dict[tuple[str, tuple[Any], tuple[Any]], MemoizationStats]):
        self.map_values: dict[tuple[str, tuple[Any], tuple[Any]], Any] = map_values
        self.map_stats: dict[tuple[str, tuple[Any], tuple[Any]], MemoizationStats] = map_stats

    def memoized_function_call(self, function_name: str, function_callable: Callable, parameters: list[Any],
                               hidden_parameters: list[Any]) -> Any:
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
        value_memory = sys.getsizeof(result)
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
