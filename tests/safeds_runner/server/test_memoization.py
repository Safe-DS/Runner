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
from safeds_runner.server._pipeline_manager import PipelineProcess, file_mtime, memoized_static_call, memoized_dynamic_call


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
    def __init__(self):
        pass

    def method1(self) -> int:
        return 1

    def method2(self, default: int = 5) -> int:
        return 1 * default


class ChildClass(BaseClass):
    def __init__(self):
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
        ("method2", lambda instance, *_: instance.method2(default=7), [BaseClass(), 7], [], "tests.safeds_runner.server.test_memoization.BaseClass.method2"),
        ("method2", lambda instance, *_: instance.method2(default=7), [ChildClass(), 7], [], "tests.safeds_runner.server.test_memoization.ChildClass.method2"),
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
        ("method2", lambda instance, *_: instance.method2(default=7), [ChildClass(), 7], [], "tests.safeds_runner.server.test_memoization.BaseClass.method2"),
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
