import sys
import tempfile
import time
import typing
from datetime import UTC, datetime
from pathlib import Path
from queue import Queue
from typing import Any

import pytest
from safeds_runner.server import _pipeline_manager
from safeds_runner.server._memoization_map import (
    MemoizationMap,
    MemoizationStats,
)
from safeds_runner.server._memoization_strategies import (
    STAT_ORDER_LRU,
    STAT_ORDER_LRU_INVERSE,
    STAT_ORDER_MISS_RATE,
    STAT_ORDER_PRIORITY,
    STAT_ORDER_TIME_SAVED,
    StatOrderExtractor,
)
from safeds_runner.server._memoization_utils import _make_hashable
from safeds_runner.server._messages import MessageDataProgram, ProgramMainInformation
from safeds_runner.server._pipeline_manager import (
    PipelineProcess,
    absolute_path,
    file_mtime,
    memoized_dynamic_call,
    memoized_static_call,
)


class UnhashableClass:
    def __hash__(self) -> int:
        raise TypeError("unhashable type")


@pytest.mark.parametrize(
    argnames="function_name,params,hidden_params,expected_result",
    argvalues=[
        ("function_pure", [1, 2, 3], [], "abc"),
        ("function_impure_readfile", ["filea.txt"], [1234567891], "abc"),
    ],
    ids=["function_pure", "function_impure_readfile"],
)
def test_memoization_static_already_present_values(
    function_name: str,
    params: list,
    hidden_params: list,
    expected_result: Any,
) -> None:
    _pipeline_manager.current_pipeline = PipelineProcess(
        MessageDataProgram({}, ProgramMainInformation("", "", "")),
        "",
        Queue(),
        {},
        MemoizationMap({}, {}),
    )
    _pipeline_manager.current_pipeline.get_memoization_map()._map_values[
        (
            function_name,
            _make_hashable(params),
            _make_hashable(hidden_params),
        )
    ] = expected_result
    _pipeline_manager.current_pipeline.get_memoization_map()._map_stats[function_name] = MemoizationStats(
        [time.perf_counter_ns()],
        [],
        [],
        [sys.getsizeof(expected_result)],
    )
    result = _pipeline_manager.memoized_static_call(function_name, lambda *_: None, params, hidden_params)
    assert result == expected_result


@pytest.mark.parametrize(
    argnames="function_name,function,params,hidden_params,expected_result",
    argvalues=[
        ("function_pure", lambda a, b, c: a + b + c, [1, 2, 3], [], 6),
        ("function_impure_readfile", lambda filename: filename.split(".")[0], ["abc.txt"], [1234567891], "abc"),
        ("function_dict", lambda x: len(x), [{}], [], 0),
        ("function_lambda", lambda x: x(), [lambda: 0], [], 0),
    ],
    ids=["function_pure", "function_impure_readfile", "function_dict", "function_lambda"],
)
def test_memoization_static_not_present_values(
    function_name: str,
    function: typing.Callable,
    params: list,
    hidden_params: list,
    expected_result: Any,
) -> None:
    _pipeline_manager.current_pipeline = PipelineProcess(
        MessageDataProgram({}, ProgramMainInformation("", "", "")),
        "",
        Queue(),
        {},
        MemoizationMap({}, {}),
    )
    # Save value in map
    result = memoized_static_call(function_name, function, params, hidden_params)
    assert result == expected_result
    # Test if value is actually saved by calling another function that does not return the expected result
    result2 = memoized_static_call(function_name, lambda *_: None, params, hidden_params)
    assert result2 == expected_result


class BaseClass:
    def __init__(self) -> None:
        pass

    def method1(self) -> int:
        return 1

    def method2(self, default: int = 5) -> int:
        return 1 * default


class ChildClass(BaseClass):
    def __init__(self) -> None:
        super().__init__()

    def method1(self) -> int:
        return 2

    def method2(self, default: int = 3) -> int:
        return 2 * default


@pytest.mark.parametrize(
    argnames="function_name,function,params,hidden_params,expected_result",
    argvalues=[
        ("method1", None, [BaseClass()], [], 1),
        ("method1", None, [ChildClass()], [], 2),
        ("method2", lambda instance, *_: instance.method2(default=7), [BaseClass(), 7], [], 7),
        ("method2", lambda instance, *_: instance.method2(default=7), [ChildClass(), 7], [], 14),
    ],
    ids=["member_call_base", "member_call_child", "member_call_base_lambda", "member_call_child_lambda"],
)
def test_memoization_dynamic(
    function_name: str,
    function: typing.Callable | None,
    params: list,
    hidden_params: list,
    expected_result: Any,
) -> None:
    _pipeline_manager.current_pipeline = PipelineProcess(
        MessageDataProgram({}, ProgramMainInformation("", "", "")),
        "",
        Queue(),
        {},
        MemoizationMap({}, {}),
    )
    # Save value in map
    result = memoized_dynamic_call(function_name, function, params, hidden_params)
    assert result == expected_result
    # Test if value is actually saved by calling another function that does not return the expected result
    result2 = memoized_dynamic_call(function_name, lambda *_: None, params, hidden_params)
    assert result2 == expected_result


@pytest.mark.parametrize(
    argnames="function_name,function,params,hidden_params,fully_qualified_function_name",
    argvalues=[
        ("method1", None, [BaseClass()], [], "tests.safeds_runner.server.test_memoization.BaseClass.method1"),
        ("method1", None, [ChildClass()], [], "tests.safeds_runner.server.test_memoization.ChildClass.method1"),
        (
            "method2",
            lambda instance, *_: instance.method2(default=7),
            [BaseClass(), 7],
            [],
            "tests.safeds_runner.server.test_memoization.BaseClass.method2",
        ),
        (
            "method2",
            lambda instance, *_: instance.method2(default=7),
            [ChildClass(), 7],
            [],
            "tests.safeds_runner.server.test_memoization.ChildClass.method2",
        ),
    ],
    ids=["member_call_base", "member_call_child", "member_call_base_lambda", "member_call_child_lambda"],
)
def test_memoization_dynamic_contains_correct_fully_qualified_name(
    function_name: str,
    function: typing.Callable | None,
    params: list,
    hidden_params: list,
    fully_qualified_function_name: Any,
) -> None:
    _pipeline_manager.current_pipeline = PipelineProcess(
        MessageDataProgram({}, ProgramMainInformation("", "", "")),
        "",
        Queue(),
        {},
        MemoizationMap({}, {}),
    )
    # Save value in map
    result = memoized_dynamic_call(function_name, function, params, hidden_params)
    # Test if value is actually saved with the correct function name
    result2 = memoized_static_call(fully_qualified_function_name, lambda *_: None, params, hidden_params)
    assert result == result2


@pytest.mark.parametrize(
    argnames="function_name,function,params,hidden_params,fully_qualified_function_name",
    argvalues=[
        ("method1", None, [ChildClass()], [], "tests.safeds_runner.server.test_memoization.BaseClass.method1"),
        (
            "method2",
            lambda instance, *_: instance.method2(default=7),
            [ChildClass(), 7],
            [],
            "tests.safeds_runner.server.test_memoization.BaseClass.method2",
        ),
    ],
    ids=["member_call_child", "member_call_child_lambda"],
)
def test_memoization_dynamic_not_base_name(
    function_name: str,
    function: typing.Callable | None,
    params: list,
    hidden_params: list,
    fully_qualified_function_name: Any,
) -> None:
    _pipeline_manager.current_pipeline = PipelineProcess(
        MessageDataProgram({}, ProgramMainInformation("", "", "")),
        "",
        Queue(),
        {},
        MemoizationMap({}, {}),
    )
    # Save value in map
    result = memoized_dynamic_call(function_name, function, params, hidden_params)
    # Test if value is actually saved with the correct function name
    result2 = memoized_static_call(fully_qualified_function_name, lambda *_: None, params, hidden_params)
    assert result is not None
    assert result2 is None


@pytest.mark.parametrize(
    argnames="function_name,function,params,hidden_params,expected_result",
    argvalues=[
        ("unhashable_params", lambda a: type(a).__name__, [UnhashableClass()], [], "UnhashableClass"),
        ("unhashable_hidden_params", lambda: None, [], [UnhashableClass()], None),
    ],
    ids=["unhashable_params", "unhashable_hidden_params"],
)
def test_memoization_static_unhashable_values(
    function_name: str,
    function: typing.Callable,
    params: list,
    hidden_params: list,
    expected_result: Any,
) -> None:
    _pipeline_manager.current_pipeline = PipelineProcess(
        MessageDataProgram({}, ProgramMainInformation("", "", "")),
        "",
        Queue(),
        {},
        MemoizationMap({}, {}),
    )
    result = memoized_static_call(function_name, function, params, hidden_params)
    assert result == expected_result


def test_file_mtime_exists() -> None:
    with tempfile.NamedTemporaryFile() as file:
        mtime = file_mtime(file.name)
        assert mtime is not None


def test_file_mtime_not_exists() -> None:
    mtime = file_mtime(f"file_not_exists.{datetime.now(tz=UTC).timestamp()}")
    assert mtime is None


def test_absolute_path() -> None:
    result = absolute_path("table.csv")
    assert Path(result).is_absolute()


@pytest.mark.parametrize(
    argnames="cache,greater_than_zero",
    argvalues=[(MemoizationMap({}, {}), False), (MemoizationMap({}, {"a": MemoizationStats([], [], [], [20])}), True)],
    ids=["cache_empty", "cache_not_empty"],
)
def test_memoization_map_cache_size(cache: MemoizationMap, greater_than_zero: bool) -> None:
    assert (cache.get_cache_size() > 0) == greater_than_zero


@pytest.mark.parametrize(
    argnames="cache,max_size,needed_capacity",
    argvalues=[
        (MemoizationMap({("a", (), ()): "12345678901234567890"}, {"a": MemoizationStats([], [], [], [20])}), 25, 20),
    ],
    ids=["cache_not_empty"],
)
def test_memoization_map_ensure_capacity(cache: MemoizationMap, max_size: int, needed_capacity: int) -> None:
    cache.max_size = max_size
    cache.ensure_capacity(needed_capacity)
    assert cache.max_size - cache.get_cache_size() >= needed_capacity


@pytest.mark.parametrize(
    argnames="cache,needed_capacity",
    argvalues=[
        (MemoizationMap({("a", (), ()): "12345678901234567890"}, {"a": MemoizationStats([], [], [], [20])}), 35),
    ],
    ids=["cache_not_empty"],
)
def test_memoization_map_ensure_capacity_unlimited(cache: MemoizationMap, needed_capacity: int) -> None:
    cache.max_size = None
    size_before_potential_shrink = cache.get_cache_size()
    cache.ensure_capacity(needed_capacity)
    assert size_before_potential_shrink == cache.get_cache_size()


@pytest.mark.parametrize(
    argnames="cache,max_size,needed_capacity",
    argvalues=[
        (MemoizationMap({("a", (), ()): "12345678901234567890"}, {"a": MemoizationStats([], [], [], [20])}), 20, 35),
    ],
    ids=["cache_not_empty"],
)
def test_memoization_map_ensure_larger_than_capacity_no_eviction(
    cache: MemoizationMap,
    max_size: int,
    needed_capacity: int,
) -> None:
    cache.max_size = max_size
    size_before_potential_shrink = cache.get_cache_size()
    cache.ensure_capacity(needed_capacity)
    assert size_before_potential_shrink == cache.get_cache_size()


@pytest.mark.parametrize(
    argnames="cache,max_size,needed_capacity,freeing_strategy",
    argvalues=[
        (
            MemoizationMap(
                {("a", (), ()): "12345678901234567890", ("b", (), ()): "12345678901234567890"},
                {
                    "a": MemoizationStats([10], [30, 30], [40], [20]),
                    "b": MemoizationStats([10], [30, 30], [40, 40], [20]),
                },
            ),
            45,
            15,
            STAT_ORDER_MISS_RATE,
        ),
        (
            MemoizationMap(
                {("a", (), ()): "12345678901234567890", ("b", (), ()): "12345678901234567890"},
                {
                    "b": MemoizationStats([5], [30, 30], [40, 40], [20]),
                    "a": MemoizationStats([10], [30, 30], [40, 40], [20]),
                },
            ),
            45,
            15,
            STAT_ORDER_LRU,
        ),
        (
            MemoizationMap(
                {("a", (), ()): "12345678901234567890", ("b", (), ()): "12345678901234567890"},
                {
                    "b": MemoizationStats([10], [30, 30], [40, 40], [20]),
                    "a": MemoizationStats([10], [30, 30], [80, 80], [20]),
                },
            ),
            45,
            15,
            STAT_ORDER_TIME_SAVED,
        ),
        (
            MemoizationMap(
                {("a", (), ()): "12345678901234567890", ("b", (), ()): "12345678901234567890"},
                {
                    "b": MemoizationStats([10], [30, 30], [40, 40], [30]),
                    "a": MemoizationStats([10], [30, 30], [40, 40], [10]),
                },
            ),
            45,
            15,
            STAT_ORDER_PRIORITY,
        ),
        (
            MemoizationMap(
                {("a", (), ()): "12345678901234567890", ("b", (), ()): "12345678901234567890"},
                {
                    "b": MemoizationStats([10], [30, 30], [40, 40], [20]),
                    "a": MemoizationStats([5], [30, 30], [40, 40], [20]),
                },
            ),
            45,
            15,
            STAT_ORDER_LRU_INVERSE,
        ),
    ],
    ids=[
        "cache_strategy_miss_rate",
        "cache_strategy_miss_lru",
        "cache_strategy_time_saved",
        "cache_strategy_priority",
        "cache_strategy_miss_lru_inverse",
    ],
)
def test_memoization_map_remove_worst_element_strategy(
    cache: MemoizationMap,
    max_size: int,
    needed_capacity: int,
    freeing_strategy: StatOrderExtractor,
) -> None:
    cache.max_size = max_size
    cache.value_removal_strategy = freeing_strategy
    free_size = cache.max_size - cache.get_cache_size()
    cache.remove_worst_element(needed_capacity - free_size)
    assert "a" in cache._map_stats
    assert "b" not in cache._map_stats


@pytest.mark.parametrize(
    argnames="function_name,function,params,hidden_params,expected_result",
    argvalues=[
        ("function_pure", lambda a, b, c: a + b + c, [1, 2, 3], [], 6),
        ("function_impure_readfile", lambda filename: filename.split(".")[0], ["abc.txt"], [1234567891], "abc"),
        ("function_dict", lambda x: len(x), [{}], [], 0),
        ("function_lambda", lambda x: x(), [lambda: 0], [], 0),
    ],
    ids=["function_pure", "function_impure_readfile", "function_dict", "function_lambda"],
)
def test_memoization_limited_static_not_present_values(
    function_name: str,
    function: typing.Callable,
    params: list,
    hidden_params: list,
    expected_result: Any,
) -> None:
    memo_map = MemoizationMap(
        {("a", (), ()): "12345678901234567890", ("b", (), ()): "12345678901234567890"},
        {"a": MemoizationStats([10], [30], [40], [20]), "b": MemoizationStats([10], [30], [40], [20])},
    )
    memo_map.max_size = 45
    _pipeline_manager.current_pipeline = PipelineProcess(
        MessageDataProgram({}, ProgramMainInformation("", "", "")),
        "",
        Queue(),
        {},
        memo_map,
    )
    # Save value in map
    result = memoized_static_call(function_name, function, params, hidden_params)
    assert result == expected_result
    # Test if value is actually saved by calling another function that does not return the expected result
    result2 = memoized_static_call(function_name, lambda *_: None, params, hidden_params)
    assert result2 == expected_result
    assert len(memo_map._map_values.items()) < 3
