import sys
import tempfile
import time
import typing
from datetime import UTC, datetime
from queue import Queue
from typing import Any

import pytest
from safeds_runner.server import pipeline_manager, memoization_map
from safeds_runner.server.memoization_map import MemoizationMap, MemoizationStats
from safeds_runner.server.messages import MessageDataProgram, ProgramMainInformation
from safeds_runner.server.pipeline_manager import PipelineProcess


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
    pipeline_manager.current_pipeline = PipelineProcess(
        MessageDataProgram({}, ProgramMainInformation("", "", "")),
        "",
        Queue(),
        {},
        MemoizationMap({}, {}),
    )
    pipeline_manager.current_pipeline.get_memoization_map().map_values[
        (
            function_name,
            memoization_map._convert_list_to_tuple(params),
            memoization_map._convert_list_to_tuple(hidden_params),
        )
    ] = expected_result
    pipeline_manager.current_pipeline.get_memoization_map().map_stats[
        (
            function_name,
            memoization_map._convert_list_to_tuple(params),
            memoization_map._convert_list_to_tuple(hidden_params),
        )
    ] = MemoizationStats(time.perf_counter_ns(), 0, 0, sys.getsizeof(expected_result))
    result = pipeline_manager.runner_memoized_function_call(function_name, lambda *_: None, params, hidden_params)
    assert result == expected_result


@pytest.mark.parametrize(
    argnames="function_name,function,params,hidden_params,expected_result",
    argvalues=[
        ("function_pure", lambda a, b, c: a + b + c, [1, 2, 3], [], 6),
        ("function_impure_readfile", lambda filename: filename.split(".")[0], ["abc.txt"], [1234567891], "abc"),
    ],
    ids=["function_pure", "function_impure_readfile"],
)
def test_memoization_not_present_values(
    function_name: str,
    function: typing.Callable,
    params: list,
    hidden_params: list,
    expected_result: Any,
) -> None:
    pipeline_manager.current_pipeline = PipelineProcess(
        MessageDataProgram({}, ProgramMainInformation("", "", "")),
        "",
        Queue(),
        {},
        MemoizationMap({}, {}),
    )
    # Save value in map
    result = pipeline_manager.runner_memoized_function_call(function_name, function, params, hidden_params)
    assert result == expected_result
    # Test if value is actually saved by calling another function that does not return the expected result
    result2 = pipeline_manager.runner_memoized_function_call(function_name, lambda *_: None, params, hidden_params)
    assert result2 == expected_result


def test_file_mtime_exists() -> None:
    with tempfile.NamedTemporaryFile() as file:
        file_mtime = pipeline_manager.runner_filemtime(file.name)
        assert file_mtime is not None


def test_file_mtime_not_exists() -> None:
    file_mtime = pipeline_manager.runner_filemtime(f"file_not_exists.{datetime.now(tz=UTC).timestamp()}")
    assert file_mtime is None
