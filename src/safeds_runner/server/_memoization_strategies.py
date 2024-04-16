"""Module that contains different memoization strategies."""

from collections.abc import Callable
from typing import Any, TypeAlias

from safeds_runner.server._memoization_stats import MemoizationStats

# Callable = Stat Key Extractor, Boolean = Reverse Order
StatOrderExtractor: TypeAlias = Callable[[tuple[str, MemoizationStats]], float]


# Sort functions by miss-rate in reverse (max. misses first)
def _stat_order_miss_rate(function_stats: tuple[str, MemoizationStats]) -> float:
    return -(len(function_stats[1].computation_times) / max(1, len(function_stats[1].lookup_times)))


STAT_ORDER_MISS_RATE: StatOrderExtractor = _stat_order_miss_rate


# Sort functions by LRU (last access timestamp, in ascending order, least recently used first)
def _stat_order_lru(function_stats: tuple[str, MemoizationStats]) -> float:
    return max(function_stats[1].access_timestamps)


STAT_ORDER_LRU: StatOrderExtractor = _stat_order_lru


# Sort functions by time saved (difference average computation time and average lookup time, least time saved first)
def _stat_order_time_saved(function_stats: tuple[str, MemoizationStats]) -> float:
    return (sum(function_stats[1].computation_times) / max(1, len(function_stats[1].computation_times))) - (
        sum(function_stats[1].lookup_times) / max(1, len(function_stats[1].lookup_times))
    )


STAT_ORDER_TIME_SAVED: StatOrderExtractor = _stat_order_time_saved


# Sort functions by priority (ratio average computation time to average size, lowest priority first)
def _stat_order_priority(function_stats: tuple[str, MemoizationStats]) -> float:
    return (sum(function_stats[1].computation_times) / max(1, len(function_stats[1].computation_times))) / max(
        1.0,
        (sum(function_stats[1].memory_sizes) / max(1, len(function_stats[1].memory_sizes))),
    )


STAT_ORDER_PRIORITY: StatOrderExtractor = _stat_order_priority


# Sort functions by inverse LRU (last access timestamp, in descending order, least recently used last)
def _stat_order_lru_inverse(function_stats: tuple[str, MemoizationStats]) -> float:
    return -max(function_stats[1].access_timestamps)


STAT_ORDER_LRU_INVERSE: StatOrderExtractor = _stat_order_lru_inverse
