from __future__ import annotations

import asyncio
import json
import logging
import multiprocessing
import re
import sys
import time
from typing import TYPE_CHECKING, Any

import pytest
import simple_websocket
from pydantic import ValidationError
from quart.testing.connections import WebsocketDisconnectError
from safeds.data.tabular.containers import Table

import safeds_runner.server.main
from safeds_runner.server._json_encoder import SafeDsEncoder
from safeds_runner.server._messages import (
    Message,
    ProgramMessageData,
    QueryMessageData,
    QueryMessageWindow,
    create_placeholder_description,
    create_placeholder_value,
    create_runtime_progress_done,
    message_type_placeholder_type,
    message_type_placeholder_value,
    message_type_runtime_error,
    message_type_runtime_progress,
    parse_validate_message,
)
from safeds_runner.server._server import SafeDsServer

if TYPE_CHECKING:
    from regex import Regex


@pytest.mark.parametrize(
    argnames="websocket_message",
    argvalues=[
        "<invalid message>",
        json.dumps({"id": "a", "data": "b"}),
        json.dumps({"type": "a", "data": "b"}),
        json.dumps({"type": "b", "id": "123"}),
        json.dumps({"type": {"program": "2"}, "id": "123", "data": "a"}),
        json.dumps({"type": "c", "id": {"": "1233"}, "data": "a"}),
        json.dumps({"type": "program", "id": "1234", "data": "a"}),
        json.dumps({"type": "placeholder_query", "id": "123", "data": "abc"}),
        json.dumps({"type": "placeholder_query", "id": "123", "data": {"a": "v"}}),
        json.dumps(
            {
                "type": "placeholder_query",
                "id": "123",
                "data": {"name": "v", "window": {"begin": "a"}},
            },
        ),
        json.dumps(
            {
                "type": "placeholder_query",
                "id": "123",
                "data": {"name": "v", "window": {"size": "a"}},
            },
        ),
        json.dumps(
            {
                "type": "program",
                "id": "1234",
                "data": {"main": {"modulepath": "1", "module": "2", "pipeline": "3"}},
            },
        ),
        json.dumps({"type": "program", "id": "1234", "data": {"code": {"": {"entry": ""}}}}),
        json.dumps(
            {
                "type": "program",
                "id": "1234",
                "data": {
                    "code": {"": {"entry": ""}},
                    "main": {"modulepath": "1", "module": "2"},
                },
            },
        ),
        json.dumps(
            {
                "type": "program",
                "id": "1234",
                "data": {
                    "code": {"": {"entry": ""}},
                    "main": {"modulepath": "1", "pipeline": "3"},
                },
            },
        ),
        json.dumps(
            {
                "type": "program",
                "id": "1234",
                "data": {
                    "code": {"": {"entry": ""}},
                    "main": {"module": "2", "pipeline": "3"},
                },
            },
        ),
        json.dumps(
            {
                "type": "program",
                "id": "1234",
                "data": {
                    "code": {"": {"entry": ""}},
                    "main": {
                        "modulepath": "1",
                        "module": "2",
                        "pipeline": "3",
                        "other": "4",
                    },
                },
            },
        ),
        json.dumps(
            {
                "type": "program",
                "id": "1234",
                "data": {
                    "code": {"": {"entry": ""}},
                    "main": {
                        "modulepath": "1",
                        "module": "2",
                        "pipeline": "3",
                        "other": {"4": "a"},
                    },
                },
            },
        ),
        json.dumps(
            {
                "type": "program",
                "id": "1234",
                "data": {
                    "code": "a",
                    "main": {"modulepath": "1", "module": "2", "pipeline": "3"},
                },
            },
        ),
        json.dumps(
            {
                "type": "program",
                "id": "1234",
                "data": {
                    "code": {"": "a"},
                    "main": {"modulepath": "1", "module": "2", "pipeline": "3"},
                },
            },
        ),
        json.dumps(
            {
                "type": "program",
                "id": "1234",
                "data": {
                    "code": {"": {"a": {"b": "c"}}},
                    "main": {"modulepath": "1", "module": "2", "pipeline": "3"},
                },
            },
        ),
    ],
    ids=[
        "no_json",
        "any_no_type",
        "any_no_id",
        "any_no_data",
        "any_invalid_type",
        "any_invalid_id",
        "program_invalid_data",
        "placeholder_query_invalid_data1",
        "placeholder_query_invalid_data2",
        "placeholder_query_invalid_data3",
        "placeholder_query_invalid_data4",
        "program_no_code",
        "program_no_main",
        "program_invalid_main1",
        "program_invalid_main2",
        "program_invalid_main3",
        "program_invalid_main4",
        "program_invalid_main5",
        "program_invalid_code1",
        "program_invalid_code2",
        "program_invalid_code3",
    ],
)
@pytest.mark.asyncio
async def test_should_fail_message_validation_ws(websocket_message: str) -> None:
    sds_server = SafeDsServer()
    test_client = sds_server._app.test_client()
    async with test_client.websocket("/WSMain") as test_websocket:
        await test_websocket.send(websocket_message)
        disconnected = False
        try:
            _result = await test_websocket.receive()
        except WebsocketDisconnectError as _disconnect:
            disconnected = True
        assert disconnected
    sds_server.shutdown()


@pytest.mark.parametrize(
    argnames=("websocket_message", "exception_message"),
    argvalues=[
        ("<invalid message>", "Invalid Message: not JSON"),
        (json.dumps({"id": "a", "data": "b"}), "Invalid Message: no type"),
        (json.dumps({"type": "a", "data": "b"}), "Invalid Message: no id"),
        (json.dumps({"type": "b", "id": "123"}), "Invalid Message: no data"),
        (
            json.dumps({"type": {"program": "2"}, "id": "123", "data": "a"}),
            "Invalid Message: invalid type",
        ),
        (
            json.dumps({"type": "c", "id": {"": "1233"}, "data": "a"}),
            "Invalid Message: invalid id",
        ),
    ],
    ids=[
        "no_json",
        "any_no_type",
        "any_no_id",
        "any_no_data",
        "any_invalid_type",
        "any_invalid_id",
    ],
)
def test_should_fail_message_validation_reason_general(websocket_message: str, exception_message: str) -> None:
    received_object, error_detail, error_short = parse_validate_message(websocket_message)
    assert error_short == exception_message


@pytest.mark.parametrize(
    argnames=("data", "exception_regex"),
    argvalues=[
        (
            {"main": {"modulepath": "1", "module": "2", "pipeline": "3"}},
            re.compile(r"code[\s\S]*missing"),
        ),
        (
            {"code": {"": {"entry": ""}}},
            re.compile(r"main[\s\S]*missing"),
        ),
        (
            {"code": {"": {"entry": ""}}, "main": {"modulepath": "1", "module": "2"}},
            re.compile(r"main.pipeline[\s\S]*missing"),
        ),
        (
            {"code": {"": {"entry": ""}}, "main": {"modulepath": "1", "pipeline": "3"}},
            re.compile(r"main.module[\s\S]*missing"),
        ),
        (
            {"code": {"": {"entry": ""}}, "main": {"module": "2", "pipeline": "3"}},
            re.compile(r"main.modulepath[\s\S]*missing"),
        ),
        (
            {
                "code": {"": {"entry": ""}},
                "main": {
                    "modulepath": "1",
                    "module": "2",
                    "pipeline": "3",
                    "other": "4",
                },
            },
            re.compile(r"main.other[\s\S]*extra_forbidden"),
        ),
        (
            {"code": "a", "main": {"modulepath": "1", "module": "2", "pipeline": "3"}},
            re.compile(r"code[\s\S]*dict_type"),
        ),
        (
            {
                "code": {"a": "n"},
                "main": {"modulepath": "1", "module": "2", "pipeline": "3"},
            },
            re.compile(r"code\.a[\s\S]*dict_type"),
        ),
        (
            {
                "code": {"a": {"b": {"c": "d"}}},
                "main": {"modulepath": "1", "module": "2", "pipeline": "3"},
            },
            re.compile(r"code\.a\.b[\s\S]*string_type"),
        ),
        (
            {
                "code": {},
                "main": {"modulepath": "1", "module": "2", "pipeline": "3"},
                "cwd": 1,
            },
            re.compile(r"cwd[\s\S]*string_type"),
        ),
    ],
    ids=[
        "program_no_code",
        "program_no_main",
        "program_invalid_main1",
        "program_invalid_main2",
        "program_invalid_main3",
        "program_invalid_main4",
        "program_invalid_code1",
        "program_invalid_code2",
        "program_invalid_code3",
        "program_invalid_cwd",
    ],
)
def test_should_fail_message_validation_reason_program(data: dict[str, Any], exception_regex: str) -> None:
    with pytest.raises(ValidationError, match=exception_regex):
        ProgramMessageData(**data)


@pytest.mark.parametrize(
    argnames=("data", "exception_regex"),
    argvalues=[
        (
            {"a": "v"},
            re.compile(r"name[\s\S]*missing"),
        ),
        (
            {"name": "v", "window": {"begin": "a"}},
            re.compile(r"window.begin[\s\S]*int_parsing"),
        ),
        (
            {"name": "v", "window": {"size": "a"}},
            re.compile(r"window.size[\s\S]*int_parsing"),
        ),
    ],
    ids=[
        "missing_name",
        "wrong_type_begin",
        "wrong_type_size",
    ],
)
def test_should_fail_message_validation_reason_placeholder_query(
    data: dict[str, Any],
    exception_regex: Regex,
) -> None:
    with pytest.raises(ValidationError, match=exception_regex):
        QueryMessageData(**data)


@pytest.mark.parametrize(
    argnames=("message", "expected_response_runtime_error"),
    argvalues=[
        (
            json.dumps(
                {
                    "type": "program",
                    "id": "abcdefgh",
                    "data": {
                        "code": {
                            "": {
                                "gen_test_a": "def pipe():\n\traise Exception('Test Exception')\n",
                                "gen_test_a_pipe": "from gen_test_a import pipe\n\nif __name__ == '__main__':\n\tpipe()",
                            },
                        },
                        "main": {
                            "modulepath": "",
                            "module": "test_a",
                            "pipeline": "pipe",
                        },
                    },
                },
            ),
            Message(message_type_runtime_error, "abcdefgh", {"message": "Test Exception"}),
        ),
    ],
    ids=["raise_exception"],
)
@pytest.mark.asyncio
async def test_should_execute_pipeline_return_exception(
    message: str,
    expected_response_runtime_error: Message,
) -> None:
    sds_server = SafeDsServer()
    test_client = sds_server._app.test_client()
    async with test_client.websocket("/WSMain") as test_websocket:
        await test_websocket.send(message)
        received_message = await test_websocket.receive()
        exception_message = Message.from_dict(json.loads(received_message))
        assert exception_message.type == expected_response_runtime_error.type
        assert exception_message.id == expected_response_runtime_error.id
        assert isinstance(exception_message.data, dict)
        assert exception_message.data["message"] == expected_response_runtime_error.data["message"]
        assert isinstance(exception_message.data["backtrace"], list)
        assert len(exception_message.data["backtrace"]) > 0
        for frame in exception_message.data["backtrace"]:
            assert "file" in frame
            assert isinstance(frame["file"], str)
            assert "line" in frame
            assert isinstance(frame["line"], int)
    sds_server.shutdown()


@pytest.mark.parametrize(
    argnames=("initial_messages", "initial_execution_message_wait", "appended_messages", "expected_responses"),
    argvalues=[
        (
            [
                json.dumps(
                    {
                        "type": "program",
                        "id": "abcdefg",
                        "data": {
                            "code": {
                                "": {
                                    "gen_test_a": (
                                        "import safeds_runner\n"
                                        "import base64\n"
                                        "from safeds.data.labeled.containers import TabularDataset\n"
                                        "from safeds.data.tabular.containers import Table\n"
                                        "from safeds.data.tabular.containers import Column\n"
                                        "from safeds.data.image.containers import Image\n"
                                        "from safeds_runner.server._json_encoder import SafeDsEncoder\n\n"
                                        "def pipe():\n"
                                        "\tvalue1 = 1\n"
                                        "\tsafeds_runner.save_placeholder('value1', value1)\n"
                                        "\tsafeds_runner.save_placeholder('col', Column('a', []))\n"
                                        "\tsafeds_runner.save_placeholder('image', Image.from_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC')))\n"
                                        "\ttable = safeds_runner.memoized_static_call(\"safeds.data.tabular.containers.Table.from_dict\", Table.from_dict, [{'a': [1, 2], 'b': [3, 4]}], {}, [])\n"
                                        "\tsafeds_runner.save_placeholder('table', table)\n"
                                        "\tdataset = TabularDataset({'a': [1, 2], 'b': [3, 4]}, 'a')\n"
                                        "\tsafeds_runner.save_placeholder('dataset', dataset)\n"
                                        '\tobject_mem = safeds_runner.memoized_static_call("random.object.call", SafeDsEncoder, [], {}, [])\n'
                                        "\tsafeds_runner.save_placeholder('object_mem',object_mem)\n"
                                    ),
                                    "gen_test_a_pipe": (
                                        "from gen_test_a import pipe\n\nif __name__ == '__main__':\n\tpipe()"
                                    ),
                                },
                            },
                            "main": {
                                "modulepath": "",
                                "module": "test_a",
                                "pipeline": "pipe",
                            },
                        },
                    },
                ),
            ],
            6,
            [
                # Query Placeholder
                json.dumps(
                    {
                        "type": "placeholder_query",
                        "id": "abcdefg",
                        "data": {"name": "value1", "window": {}},
                    },
                ),
                # Query Placeholder (memoized type)
                json.dumps(
                    {
                        "type": "placeholder_query",
                        "id": "abcdefg",
                        "data": {"name": "table", "window": {}},
                    },
                ),
                # Query Placeholder (memoized type)
                json.dumps(
                    {
                        "type": "placeholder_query",
                        "id": "abcdefg",
                        "data": {"name": "dataset", "window": {}},
                    },
                ),
                # Query not displayable Placeholder
                json.dumps(
                    {
                        "type": "placeholder_query",
                        "id": "abcdefg",
                        "data": {"name": "col", "window": {}},
                    },
                ),
                # Query invalid placeholder
                json.dumps(
                    {
                        "type": "placeholder_query",
                        "id": "abcdefg",
                        "data": {"name": "value2", "window": {}},
                    },
                ),
            ],
            [
                # Validate Placeholder Information
                Message(
                    message_type_placeholder_type,
                    "abcdefg",
                    create_placeholder_description("value1", "Int"),
                ),
                Message(
                    message_type_placeholder_type,
                    "abcdefg",
                    create_placeholder_description("col", "Column"),
                ),
                Message(
                    message_type_placeholder_type,
                    "abcdefg",
                    create_placeholder_description("image", "Image"),
                ),
                Message(
                    message_type_placeholder_type,
                    "abcdefg",
                    create_placeholder_description("table", "Table"),
                ),
                Message(
                    message_type_placeholder_type,
                    "abcdefg",
                    create_placeholder_description("dataset", "Table"),
                ),
                Message(
                    message_type_placeholder_type,
                    "abcdefg",
                    create_placeholder_description("object_mem", "SafeDsEncoder"),
                ),
                # Validate Progress Information
                Message(
                    message_type_runtime_progress,
                    "abcdefg",
                    create_runtime_progress_done(),
                ),
                # Query Result Valid
                Message(
                    message_type_placeholder_value,
                    "abcdefg",
                    create_placeholder_value(QueryMessageData(name="value1"), "Int", 1),
                ),
                # Query Result Valid (memoized)
                Message(
                    message_type_placeholder_value,
                    "abcdefg",
                    create_placeholder_value(
                        QueryMessageData(name="table"),
                        "Table",
                        {"a": [1, 2], "b": [3, 4]},
                    ),
                ),
                # Query Result Valid
                Message(
                    message_type_placeholder_value,
                    "abcdefg",
                    create_placeholder_value(
                        QueryMessageData(name="dataset"),
                        "Table",
                        {"a": [1, 2], "b": [3, 4]},
                    ),
                ),
                # Query Result not displayable
                Message(
                    message_type_placeholder_value,
                    "abcdefg",
                    create_placeholder_value(
                        QueryMessageData(name="col"),
                        "Column",
                        "+------+\n"
                              "| a    |\n"
                              "| ---  |\n"
                              "| null |\n"
                              "+======+\n"
                              "+------+",
                    ),
                ),
                # Query Result Invalid
                Message(
                    message_type_placeholder_value,
                    "abcdefg",
                    create_placeholder_value(QueryMessageData(name="value2"), "", ""),
                ),
            ],
        ),
    ],
    ids=["query_valid_query_invalid"],
)
@pytest.mark.asyncio
async def test_should_execute_pipeline_return_valid_placeholder(
    initial_messages: list[str],
    initial_execution_message_wait: int,
    appended_messages: list[str],
    expected_responses: list[Message],
) -> None:
    # Initial execution
    sds_server = SafeDsServer()
    test_client = sds_server._app.test_client()
    async with test_client.websocket("/WSMain") as test_websocket:
        for message in initial_messages:
            await test_websocket.send(message)
        # Wait for at least enough messages to successfully execute pipeline
        for _ in range(initial_execution_message_wait):
            received_message = await test_websocket.receive()
            next_message = Message.from_dict(json.loads(received_message))
            assert next_message == expected_responses.pop(0)
        # Now send queries
        for message in appended_messages:
            await test_websocket.send(message)
        # And compare with expected responses
        actual_responses: list[Message] = []
        while len(actual_responses) < len(expected_responses):
            received_message = await test_websocket.receive()
            next_message = Message.from_dict(json.loads(received_message))
            actual_responses.append(next_message)

        for actual_response in actual_responses:
            assert actual_response in expected_responses

    sds_server.shutdown()


@pytest.mark.parametrize(
    argnames=("messages", "expected_response"),
    argvalues=[
        (
            [
                json.dumps(
                    {
                        "type": "program",
                        "id": "123456789",
                        "data": {
                            "code": {
                                "": {
                                    "gen_b": (
                                        "from a.stub import u\n"
                                        "from v.u.s.testing import add1\n"
                                        "\n"
                                        "def c():\n"
                                        "\ta1 = 1\n"
                                        "\ta2 = True or False\n"
                                        "\tprint('test2')\n"
                                        "\tprint('new dynamic output')\n"
                                        "\tprint(f'Add1: {add1(1, 2)}')\n"
                                        "\treturn a1 + a2\n"
                                    ),
                                    "gen_b_c": "from gen_b import c\n\nif __name__ == '__main__':\n\tc()",
                                },
                                "a": {"stub": "def u():\n\treturn 1"},
                                "v.u.s": {
                                    "testing": "import a.stub;\n\ndef add1(v1, v2):\n\treturn v1 + v2 + a.stub.u()\n",
                                },
                            },
                            "main": {"modulepath": "", "module": "b", "pipeline": "c"},
                        },
                    },
                ),
            ],
            Message(
                message_type_runtime_progress,
                "123456789",
                create_runtime_progress_done(),
            ),
        ),
        (
            # Query Result Invalid (no pipeline exists)
            [
                json.dumps(
                    {
                        "type": "invalid_message_type",
                        "id": "unknown-code-id-never-generated",
                        "data": "",
                    },
                ),
                json.dumps(
                    {
                        "type": "placeholder_query",
                        "id": "unknown-code-id-never-generated",
                        "data": {"name": "v", "window": {}},
                    },
                ),
            ],
            Message(
                message_type_placeholder_value,
                "unknown-code-id-never-generated",
                create_placeholder_value(QueryMessageData(name="v"), "", ""),
            ),
        ),
    ],
    ids=["progress_message_done", "invalid_message_invalid_placeholder_query"],
)
@pytest.mark.asyncio
async def test_should_successfully_execute_simple_flow(messages: list[str], expected_response: Message) -> None:
    sds_server = SafeDsServer()
    test_client = sds_server._app.test_client()
    async with test_client.websocket("/WSMain") as test_websocket:
        for message in messages:
            await test_websocket.send(message)
        received_message = await test_websocket.receive()
        query_result_invalid = Message.from_dict(json.loads(received_message))
        assert query_result_invalid == expected_response
    sds_server.shutdown()


@pytest.mark.parametrize(
    argnames="messages",
    argvalues=[
        [
            json.dumps({"type": "shutdown", "id": "", "data": ""}),
        ],
    ],
    ids=["shutdown_message"],
)
def test_should_shut_itself_down(messages: list[str]) -> None:
    process = multiprocessing.Process(target=helper_should_shut_itself_down_run_in_subprocess, args=(messages,))
    process.start()
    process.join(30)
    assert process.exitcode == 0


def helper_should_shut_itself_down_run_in_subprocess(sub_messages: list[str]) -> None:
    asyncio.get_event_loop().run_until_complete(helper_should_shut_itself_down_run_in_subprocess_async(sub_messages))


async def helper_should_shut_itself_down_run_in_subprocess_async(
    sub_messages: list[str],
) -> None:
    sds_server = SafeDsServer()
    test_client = sds_server._app.test_client()
    async with test_client.websocket("/WSMain") as test_websocket:
        for message in sub_messages:
            await test_websocket.send(message)
    sds_server.shutdown()


@pytest.mark.timeout(45)
def test_should_accept_at_least_2_parallel_connections_in_subprocess() -> None:
    port = 6000
    server_output_pipes_stderr_r, server_output_pipes_stderr_w = multiprocessing.Pipe()
    process = multiprocessing.Process(
        target=helper_should_accept_at_least_2_parallel_connections_in_subprocess_server,
        args=(port, server_output_pipes_stderr_w),
    )
    process.start()
    while process.is_alive():
        if not server_output_pipes_stderr_r.poll(0.1):
            continue
        process_line = str(server_output_pipes_stderr_r.recv()).strip()
        # Wait for first line of log
        if process_line.startswith("INFO:root:Starting Safe-DS Runner"):
            break
    connected = False
    client1 = None
    for _i in range(10):
        try:
            client1 = simple_websocket.Client.connect(f"ws://127.0.0.1:{port}/WSMain")
            client2 = simple_websocket.Client.connect(f"ws://127.0.0.1:{port}/WSMain")
            connected = client1.connected and client2.connected
            break
        except ConnectionRefusedError as e:
            logging.warning("Connection refused: %s", e)
            connected = False
            time.sleep(0.5)
    if client1 is not None and client1.connected:
        client1.send('{"id": "", "type": "shutdown", "data": ""}')
        process.join(5)
    if process.is_alive():
        process.kill()
    assert connected


def helper_should_accept_at_least_2_parallel_connections_in_subprocess_server(
    port: int,
    pipe: multiprocessing.connection.Connection,
) -> None:
    sys.stderr.write = lambda value: pipe.send(value)  # type: ignore[method-assign, return-value]
    sys.stdout.write = lambda value: pipe.send(value)  # type: ignore[method-assign, return-value]
    safeds_runner.server.main.start_server(port)


@pytest.mark.parametrize(
    argnames=("query", "type_", "value", "result"),
    argvalues=[
        (
            QueryMessageData(name="name"),
            "Table",
            Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
            '{"name": "name", "type": "Table", "value": {"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}}',
        ),
        (
            QueryMessageData(name="name", window=QueryMessageWindow(begin=0, size=1)),
            "Table",
            Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
            (
                '{"name": "name", "type": "Table", "window": {"begin": 0, "size": 1, "max": 7}, "value": {"a": [1],'
                ' "b": [3]}}'
            ),
        ),
        (
            QueryMessageData(name="name", window=QueryMessageWindow(begin=4, size=3)),
            "Table",
            Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
            (
                '{"name": "name", "type": "Table", "window": {"begin": 4, "size": 3, "max": 7}, "value": {"a": [3, 2,'
                ' 1], "b": [1, 2, 3]}}'
            ),
        ),
        (
            QueryMessageData(name="name", window=QueryMessageWindow(begin=0, size=0)),
            "Table",
            Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
            (
                '{"name": "name", "type": "Table", "window": {"begin": 0, "size": 0, "max": 7}, "value": {"a": [], "b":'
                " []}}"
            ),
        ),
        (
            QueryMessageData(name="name", window=QueryMessageWindow(begin=4, size=30)),
            "Table",
            Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
            (
                '{"name": "name", "type": "Table", "window": {"begin": 4, "size": 3, "max": 7}, "value": {"a": [3, 2,'
                ' 1], "b": [1, 2, 3]}}'
            ),
        ),
        (
            QueryMessageData(name="name", window=QueryMessageWindow(begin=4, size=None)),
            "Table",
            Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
            (
                '{"name": "name", "type": "Table", "window": {"begin": 4, "size": 3, "max": 7}, "value": {"a": [3, 2,'
                ' 1], "b": [1, 2, 3]}}'
            ),
        ),
        (
            QueryMessageData(name="name", window=QueryMessageWindow(begin=0, size=-5)),
            "Table",
            Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
            (
                '{"name": "name", "type": "Table", "window": {"begin": 0, "size": 0, "max": 7}, "value": {"a": [], "b":'
                " []}}"
            ),
        ),
        (
            QueryMessageData(name="name", window=QueryMessageWindow(begin=-5, size=None)),
            "Table",
            Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
            (
                '{"name": "name", "type": "Table", "window": {"begin": 0, "size": 7, "max": 7}, "value": {"a": [1, 2,'
                ' 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}}'
            ),
        ),
    ],
    ids=[
        "query_nowindow",
        "query_windowed_0_1",
        "query_windowed_4_3",
        "query_windowed_empty",
        "query_windowed_size_too_large",
        "query_windowed_4_max",
        "query_windowed_negative_size",
        "query_windowed_negative_offset",
    ],
)
def test_windowed_placeholder(query: QueryMessageData, type_: str, value: Any, result: str) -> None:
    message = create_placeholder_value(query, type_, value)
    assert json.dumps(message, cls=SafeDsEncoder) == result


@pytest.mark.parametrize(
    argnames=("query", "expected_response"),
    argvalues=[
        (
            json.dumps(
                {
                    "type": "program",
                    "id": "abcdefgh",
                    "data": {
                        "code": {
                            "": {
                                "gen_test_a": "def pipe():\n\tpass\n",
                                "gen_test_a_pipe": "from gen_test_a import pipe\n\nif __name__ == '__main__':\n\tpipe()",
                            },
                        },
                        "main": {
                            "modulepath": "",
                            "module": "test_a",
                            "pipeline": "pipe",
                        },
                    },
                },
            ),
            Message(message_type_runtime_progress, "abcdefgh", "done"),
        ),
    ],
    ids=["at_least_a_message_without_crashing"],
)
@pytest.mark.timeout(45)
def test_should_accept_at_least_a_message_without_crashing_in_subprocess(
    query: str,
    expected_response: Message,
) -> None:
    port = 6000
    server_output_pipes_stderr_r, server_output_pipes_stderr_w = multiprocessing.Pipe()
    process = multiprocessing.Process(
        target=helper_should_accept_at_least_a_message_without_crashing_in_subprocess_server,
        args=(port, server_output_pipes_stderr_w),
    )
    process.start()
    while process.is_alive():
        if not server_output_pipes_stderr_r.poll(0.1):
            continue
        process_line = str(server_output_pipes_stderr_r.recv()).strip()
        # Wait for first line of log
        if process_line.startswith("INFO:root:Starting Safe-DS Runner"):
            break
    client1 = None
    for _i in range(10):
        try:
            client1 = simple_websocket.Client.connect(f"ws://127.0.0.1:{port}/WSMain")
            break
        except ConnectionRefusedError as e:
            logging.warning("Connection refused: %s", e)
            time.sleep(0.5)
    if client1 is not None and client1.connected:
        client1.send(query)
        received_message = client1.receive()
        received_message_validated = Message.from_dict(json.loads(received_message))
        assert received_message_validated == expected_response
        client1.send('{"id": "", "type": "shutdown", "data": ""}')
        process.join(5)
    if process.is_alive():
        process.kill()


def helper_should_accept_at_least_a_message_without_crashing_in_subprocess_server(
    port: int,
    pipe: multiprocessing.connection.Connection,
) -> None:
    sys.stderr.write = lambda value: pipe.send(value)  # type: ignore[method-assign, return-value]
    sys.stdout.write = lambda value: pipe.send(value)  # type: ignore[method-assign, return-value]
    safeds_runner.server.main.start_server(port)
