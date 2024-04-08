import sys
import tempfile
import time
import typing
from datetime import UTC, datetime
from queue import Queue
from typing import Any

import pytest
from safeds_runner.server import _pipeline_manager
from safeds_runner.server._memoization_map import (
    MemoizationMap,
    MemoizationStats,
    _get_size_of_value,
    _make_hashable,
)
from safeds_runner.server._messages import MessageDataProgram, ProgramMainInformation
from safeds_runner.server._pipeline_manager import PipelineProcess, file_mtime, memoized_call


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
def test_memoization_already_present_values(
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
    _pipeline_manager.current_pipeline.get_memoization_map()._map_values[(
        function_name,
        _make_hashable(params),
        _make_hashable(hidden_params),
    )] = expected_result
    _pipeline_manager.current_pipeline.get_memoization_map()._map_stats[function_name] = MemoizationStats(
        [time.perf_counter_ns()],
        [],
        [],
        [sys.getsizeof(expected_result)],
    )
    result = _pipeline_manager.memoized_call(function_name, lambda *_: None, params, hidden_params)
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
def test_memoization_not_present_values(
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
    result = memoized_call(function_name, function, params, hidden_params)
    assert result == expected_result
    # Test if value is actually saved by calling another function that does not return the expected result
    result2 = memoized_call(function_name, lambda *_: None, params, hidden_params)
    assert result2 == expected_result


@pytest.mark.parametrize(
    argnames="function_name,function,params,hidden_params,expected_result",
    argvalues=[
        ("unhashable_params", lambda a: type(a).__name__, [UnhashableClass()], [], "UnhashableClass"),
        ("unhashable_hidden_params", lambda: None, [], [UnhashableClass()], None),
    ],
    ids=["unhashable_params", "unhashable_hidden_params"],
)
def test_memoization_unhashable_values(
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

    result = memoized_call(function_name, function, params, hidden_params)
    assert result == expected_result


def test_file_mtime_exists() -> None:
    with tempfile.NamedTemporaryFile() as file:
        mtime = file_mtime(file.name)
        assert mtime is not None


def test_file_mtime_not_exists() -> None:
    mtime = file_mtime(f"file_not_exists.{datetime.now(tz=UTC).timestamp()}")
    assert mtime is None


@pytest.mark.parametrize(
    argnames="value,expected_size",
    argvalues=[
        (1, 0),
        ({}, 0),
        ({"a": "b"}, sys.getsizeof({})),
        ([], 0),
        ([1, 2, 3], sys.getsizeof([])),
        ((), 0),
        ((1, 2, 3), sys.getsizeof(())),
        (set(), 0),
        ({1, 2, 3}, sys.getsizeof(set())),
        (frozenset(), 0),
        (frozenset({1, 2, 3}), sys.getsizeof(frozenset())),
    ],
    ids=[
        "immediate",
        "dict_empty",
        "dict_values",
        "list_empty",
        "list_values",
        "tuple_empty",
        "tuple_values",
        "set_empty",
        "set_values",
        "frozenset_empty",
        "frozenset_values",
    ],
)
def test_memory_usage(value: Any, expected_size: int) -> None:
    assert _get_size_of_value(value) > expected_size
