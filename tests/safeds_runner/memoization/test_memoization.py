from __future__ import annotations

import sys
import tempfile
import time
import typing
from datetime import UTC, datetime
from pathlib import Path
from queue import Queue
from typing import Any

import pytest
from safeds_runner.memoization._memoization_map import (
    MemoizationMap,
    MemoizationStats,
)
from safeds_runner.memoization._memoization_strategies import (
    STAT_ORDER_LRU,
    STAT_ORDER_MISS_RATE,
    STAT_ORDER_MRU,
    STAT_ORDER_PRIORITY,
    STAT_ORDER_TIME_SAVED,
    StatOrderExtractor,
)
from safeds_runner.memoization._memoization_utils import _make_hashable
from safeds_runner.server import _pipeline_manager
from safeds_runner.server._pipeline_manager import (
    PipelineProcess,
    absolute_path,
    file_mtime,
    memoized_dynamic_call,
    memoized_static_call,
)
# from safeds_runner.server.messages._messages import ProgramMessageData, ProgramMessageMainInformation


class UnhashableClass:
    def __hash__(self) -> int:
        raise TypeError("unhashable type")


@pytest.mark.parametrize(
    argnames=(
        "fully_qualified_function_name",
        "positional_arguments",
        "keyword_arguments",
        "hidden_arguments",
        "expected_result",
    ),
    argvalues=[
        ("function_pure", [1, 2, 3], {}, [], "abc"),
        ("function_impure_readfile", ["filea.txt"], {}, [1234567891], "abc"),
    ],
    ids=["function_pure", "function_impure_readfile"],
)
def test_memoization_static_already_present_values(
    fully_qualified_function_name: str,
    positional_arguments: list,
    keyword_arguments: dict,
    hidden_arguments: list,
    expected_result: Any,
) -> None:
    _pipeline_manager.current_pipeline = PipelineProcess("", ProgramMessageData(code={},
                                                                                main=ProgramMessageMainInformation(
                                                                                    modulepath="", module="",
                                                                                    pipeline="")), Queue(), {},
                                                         MemoizationMap({}, {}))
    _pipeline_manager.current_pipeline.get_memoization_map()._map_values[
        (
            fully_qualified_function_name,
            _make_hashable(positional_arguments),
            _make_hashable(hidden_arguments),
        )
    ] = expected_result
    _pipeline_manager.current_pipeline.get_memoization_map()._map_stats[fully_qualified_function_name] = (
        MemoizationStats(
            [time.perf_counter_ns()],
            [],
            [],
            [sys.getsizeof(expected_result)],
        )
    )
    result = _pipeline_manager.memoized_static_call(
        fully_qualified_function_name,
        lambda *_: None,
        positional_arguments,
        keyword_arguments,
        hidden_arguments,
    )
    assert result == expected_result


@pytest.mark.parametrize(
    argnames=(
        "fully_qualified_function_name",
        "callable_",
        "positional_arguments",
        "keyword_arguments",
        "hidden_arguments",
        "expected_result",
    ),
    argvalues=[
        ("function_pure", lambda a, b, c: a + b + c, [1, 2, 3], {}, [], 6),
        ("function_impure_readfile", lambda filename: filename.split(".")[0], ["abc.txt"], {}, [1234567891], "abc"),
        ("function_dict", lambda x: len(x), [{}], {}, [], 0),
        ("function_lambda", lambda x: x(), [lambda: 0], {}, [], 0),
    ],
    ids=["function_pure", "function_impure_readfile", "function_dict", "function_lambda"],
)
def test_memoization_static_not_present_values(
    fully_qualified_function_name: str,
    callable_: typing.Callable,
    positional_arguments: list,
    keyword_arguments: dict,
    hidden_arguments: list,
    expected_result: Any,
) -> None:
    _pipeline_manager.current_pipeline = PipelineProcess("", ProgramMessageData(code={},
                                                                                main=ProgramMessageMainInformation(
                                                                                    modulepath="", module="",
                                                                                    pipeline="")), Queue(), {},
                                                         MemoizationMap({}, {}))
    # Save value in map
    result = memoized_static_call(
        fully_qualified_function_name,
        callable_,
        positional_arguments,
        keyword_arguments,
        hidden_arguments,
    )
    assert result == expected_result

    # Test if value is actually saved by calling another function that does not return the expected result
    result2 = memoized_static_call(
        fully_qualified_function_name,
        lambda *_: None,
        positional_arguments,
        keyword_arguments,
        hidden_arguments,
    )
    assert result2 == expected_result


class BaseClass:
    def __init__(self) -> None:
        pass

    def method1(self) -> int:
        return 1

    def method2(self, *, default: int = 5) -> int:
        return 1 * default


class ChildClass(BaseClass):
    def __init__(self) -> None:
        super().__init__()

    def method1(self) -> int:
        return 2

    def method2(self, *, default: int = 3) -> int:
        return 2 * default


@pytest.mark.parametrize(
    argnames=[
        "receiver",
        "function_name",
        "positional_arguments",
        "keyword_arguments",
        "hidden_arguments",
        "expected_result",
    ],
    argvalues=[
        (BaseClass(), "method1", [], {}, [], 1),
        (ChildClass(), "method1", [], {}, [], 2),
        (BaseClass(), "method2", [], {"default": 5}, [], 5),
    ],
    ids=[
        "member_call_base",
        "member_call_child",
        "member_call_keyword_only_argument",
    ],
)
def test_memoization_dynamic(
    receiver: Any,
    function_name: str,
    positional_arguments: list,
    keyword_arguments: dict,
    hidden_arguments: list,
    expected_result: Any,
) -> None:
    _pipeline_manager.current_pipeline = PipelineProcess("", ProgramMessageData(code={},
                                                                                main=ProgramMessageMainInformation(
                                                                                    modulepath="", module="",
                                                                                    pipeline="")), Queue(), {},
                                                         MemoizationMap({}, {}))

    # Save value in map
    result = memoized_dynamic_call(
        receiver,
        function_name,
        positional_arguments,
        keyword_arguments,
        hidden_arguments,
    )
    assert result == expected_result

    # Test if value is actually saved by calling another function that does not return the expected result
    result2 = memoized_dynamic_call(
        receiver,
        function_name,
        positional_arguments,
        keyword_arguments,
        hidden_arguments,
    )
    assert result2 == expected_result


@pytest.mark.parametrize(
    argnames=(
        "receiver",
        "function_name",
        "positional_arguments",
        "keyword_arguments",
        "hidden_arguments",
        "fully_qualified_function_name",
    ),
    argvalues=[
        (BaseClass(), "method1", [], {}, [], "tests.safeds_runner.memoization.test_memoization.BaseClass.method1"),
        (ChildClass(), "method1", [], {}, [], "tests.safeds_runner.memoization.test_memoization.ChildClass.method1"),
    ],
    ids=[
        "member_call_base",
        "member_call_child",
    ],
)
def test_memoization_dynamic_contains_correct_fully_qualified_name(
    receiver: Any,
    function_name: str,
    positional_arguments: list,
    keyword_arguments: dict,
    hidden_arguments: list,
    fully_qualified_function_name: Any,
) -> None:
    _pipeline_manager.current_pipeline = PipelineProcess("", ProgramMessageData(code={},
                                                                                main=ProgramMessageMainInformation(
                                                                                    modulepath="", module="",
                                                                                    pipeline="")), Queue(), {},
                                                         MemoizationMap({}, {}))
    # Save value in map
    result = memoized_dynamic_call(
        receiver,
        function_name,
        positional_arguments,
        keyword_arguments,
        hidden_arguments,
    )

    # Test if value is actually saved with the correct function name
    result2 = memoized_static_call(
        fully_qualified_function_name,
        lambda *_: None,
        [receiver, *positional_arguments],
        keyword_arguments,
        hidden_arguments,
    )

    assert result == result2


@pytest.mark.parametrize(
    argnames=(
        "receiver",
        "function_name",
        "positional_arguments",
        "keyword_arguments",
        "hidden_arguments",
        "fully_qualified_function_name",
    ),
    argvalues=[
        (ChildClass(), "method1", [], {}, [], "tests.safeds_runner.server.test_memoization.BaseClass.method1"),
    ],
    ids=[
        "member_call_child",
    ],
)
def test_memoization_dynamic_not_base_name(
    receiver: Any,
    function_name: str,
    positional_arguments: list,
    keyword_arguments: dict,
    hidden_arguments: list,
    fully_qualified_function_name: Any,
) -> None:
    _pipeline_manager.current_pipeline = PipelineProcess("", ProgramMessageData(code={},
                                                                                main=ProgramMessageMainInformation(
                                                                                    modulepath="", module="",
                                                                                    pipeline="")), Queue(), {},
                                                         MemoizationMap({}, {}))

    # Save value in map
    result = memoized_dynamic_call(
        receiver,
        function_name,
        positional_arguments,
        keyword_arguments,
        hidden_arguments,
    )

    # Test if value is actually saved with the correct function name
    result2 = memoized_static_call(
        fully_qualified_function_name,
        lambda *_: None,
        [receiver, *positional_arguments],
        keyword_arguments,
        hidden_arguments,
    )
    assert result is not None
    assert result2 is None


@pytest.mark.parametrize(
    argnames=(
        "fully_qualified_function_name",
        "callable_",
        "positional_arguments",
        "keyword_arguments",
        "hidden_arguments",
        "expected_result",
    ),
    argvalues=[
        ("unhashable_positional_argument", lambda a: type(a).__name__, [UnhashableClass()], {}, [], "UnhashableClass"),
        ("unhashable_params", lambda a: type(a).__name__, [UnhashableClass()], {}, [], "UnhashableClass"),
        ("unhashable_hidden_params", lambda: None, [], {}, [UnhashableClass()], None),
    ],
    ids=[
        "unhashable_positional_argument",
        "unhashable_keyword_argument",
        "unhashable_hidden_arguments",
    ],
)
def test_memoization_static_unhashable_values(
    fully_qualified_function_name: str,
    callable_: typing.Callable,
    positional_arguments: list,
    keyword_arguments: dict,
    hidden_arguments: list,
    expected_result: Any,
) -> None:
    _pipeline_manager.current_pipeline = PipelineProcess("", ProgramMessageData(code={},
                                                                                main=ProgramMessageMainInformation(
                                                                                    modulepath="", module="",
                                                                                    pipeline="")), Queue(), {},
                                                         MemoizationMap({}, {}))
    result = memoized_static_call(
        fully_qualified_function_name,
        callable_,
        positional_arguments,
        keyword_arguments,
        hidden_arguments,
    )
    assert result == expected_result


def test_file_mtime_exists() -> None:
    with tempfile.NamedTemporaryFile() as file:
        mtime = file_mtime(file.name)
        assert mtime is not None


def test_file_mtime_exists_list() -> None:
    with tempfile.NamedTemporaryFile() as file:
        mtime = file_mtime([file.name, file.name])
        assert isinstance(mtime, list)
        assert all(it is not None for it in mtime)


def test_file_mtime_not_exists() -> None:
    mtime = file_mtime(f"file_not_exists.{datetime.now(tz=UTC).timestamp()}")
    assert mtime is None


def test_absolute_path() -> None:
    result = absolute_path("table.csv")
    assert Path(result).is_absolute()


def test_absolute_path_list() -> None:
    result = absolute_path(["table.csv"])
    assert all(Path(it).is_absolute() for it in result)


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
            STAT_ORDER_MRU,
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
    argnames=(
        "fully_qualified_function_name",
        "callable_",
        "positional_arguments",
        "keyword_arguments",
        "hidden_arguments",
        "expected_result",
    ),
    argvalues=[
        ("function_pure", lambda a, b, c: a + b + c, [1, 2, 3], {}, [], 6),
        ("function_impure_readfile", lambda filename: filename.split(".")[0], ["abc.txt"], {}, [1234567891], "abc"),
        ("function_dict", lambda x: len(x), [{}], {}, [], 0),
        ("function_lambda", lambda x: x(), [lambda: 0], {}, [], 0),
    ],
    ids=[
        "function_pure",
        "function_impure_readfile",
        "function_dict",
        "function_lambda",
    ],
)
def test_memoization_limited_static_not_present_values(
    fully_qualified_function_name: str,
    callable_: typing.Callable,
    positional_arguments: list,
    keyword_arguments: dict,
    hidden_arguments: list,
    expected_result: Any,
) -> None:
    memo_map = MemoizationMap(
        {("a", (), ()): "12345678901234567890", ("b", (), ()): "12345678901234567890"},
        {"a": MemoizationStats([10], [30], [40], [20]), "b": MemoizationStats([10], [30], [40], [20])},
    )
    memo_map.max_size = 45
    _pipeline_manager.current_pipeline = PipelineProcess("", ProgramMessageData(code={},
                                                                                main=ProgramMessageMainInformation(
                                                                                    modulepath="", module="",
                                                                                    pipeline="")), Queue(), {},
                                                         memo_map)
    # Save value in map
    result = memoized_static_call(
        fully_qualified_function_name,
        callable_,
        positional_arguments,
        keyword_arguments,
        hidden_arguments,
    )
    assert result == expected_result

    # Test if value is actually saved by calling another function that does not return the expected result
    result2 = memoized_static_call(
        fully_qualified_function_name,
        lambda *_: None,
        positional_arguments,
        keyword_arguments,
        hidden_arguments,
    )

    assert result2 == expected_result
    assert len(memo_map._map_values.items()) < 3
