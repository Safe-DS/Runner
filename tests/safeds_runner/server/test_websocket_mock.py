import json
import os
import sys
import threading

import pytest
from safeds_runner.server.main import ws_main, app_pipeline_manager
from safeds_runner.server.messages import (
    Message,
    create_placeholder_description,
    create_placeholder_value,
    create_runtime_progress_done,
    message_type_placeholder_type,
    message_type_placeholder_value,
    message_type_runtime_error,
    message_type_runtime_progress,
)


class MockWebsocketConnection:
    def __init__(self, messages: list[str]):
        self.messages = messages
        self.received: list[str] = []
        self.close_reason: int | None = None
        self.close_message: str | None = None
        self.condition_variable = threading.Condition()

    def send(self, msg: str) -> None:
        self.received.append(msg)
        with self.condition_variable:
            self.condition_variable.notify_all()

    def receive(self) -> str | None:
        if len(self.messages) == 0:
            return None
        return self.messages.pop(0)

    def close(self, reason: int | None = None, message: str | None = None) -> None:
        self.close_reason = reason
        self.close_message = message

    def wait_for_messages(self, wait_for_messages: int = 1) -> None:
        while True:
            with self.condition_variable:
                if len(self.received) >= wait_for_messages:
                    return
                self.condition_variable.wait()


@pytest.mark.parametrize(
    argnames="websocket_message,exception_message",
    argvalues=[
        ("<invalid message>", "Invalid Message: not JSON"),
        (json.dumps({"id": "a", "data": "b"}), "Invalid Message: no type"),
        (json.dumps({"type": "a", "data": "b"}), "Invalid Message: no id"),
        (json.dumps({"type": "b", "id": "123"}), "Invalid Message: no data"),
        (json.dumps({"type": {"program": "2"}, "id": "123", "data": "a"}), "Invalid Message: invalid type"),
        (json.dumps({"type": "c", "id": {"": "1233"}, "data": "a"}), "Invalid Message: invalid id"),
        (json.dumps({"type": "program", "id": "1234", "data": "a"}), "Message data is not a JSON object"),
        (json.dumps({"type": "placeholder_query", "id": "123", "data": {"a": "v"}}), "Message data is not a string"),
        (
            json.dumps({
                "type": "program",
                "id": "1234",
                "data": {"main": {"modulepath": "1", "module": "2", "pipeline": "3"}},
            }),
            "No 'code' parameter given",
        ),
        (
            json.dumps({"type": "program", "id": "1234", "data": {"code": {"": {"entry": ""}}}}),
            "No 'main' parameter given",
        ),
        (
            json.dumps({
                "type": "program",
                "id": "1234",
                "data": {"code": {"": {"entry": ""}}, "main": {"modulepath": "1", "module": "2"}},
            }),
            "Invalid 'main' parameter given",
        ),
        (
            json.dumps({
                "type": "program",
                "id": "1234",
                "data": {"code": {"": {"entry": ""}}, "main": {"modulepath": "1", "pipeline": "3"}},
            }),
            "Invalid 'main' parameter given",
        ),
        (
            json.dumps({
                "type": "program",
                "id": "1234",
                "data": {"code": {"": {"entry": ""}}, "main": {"module": "2", "pipeline": "3"}},
            }),
            "Invalid 'main' parameter given",
        ),
        (
            json.dumps({
                "type": "program",
                "id": "1234",
                "data": {
                    "code": {"": {"entry": ""}},
                    "main": {"modulepath": "1", "module": "2", "pipeline": "3", "other": "4"},
                },
            }),
            "Invalid 'main' parameter given",
        ),
        (
            json.dumps({
                "type": "program",
                "id": "1234",
                "data": {
                    "code": {"": {"entry": ""}},
                    "main": {"modulepath": "1", "module": "2", "pipeline": "3", "other": {"4": "a"}},
                },
            }),
            "Invalid 'main' parameter given",
        ),
        (
            json.dumps({
                "type": "program",
                "id": "1234",
                "data": {"code": "a", "main": {"modulepath": "1", "module": "2", "pipeline": "3"}},
            }),
            "Invalid 'code' parameter given",
        ),
        (
            json.dumps({
                "type": "program",
                "id": "1234",
                "data": {"code": {"": "a"}, "main": {"modulepath": "1", "module": "2", "pipeline": "3"}},
            }),
            "Invalid 'code' parameter given",
        ),
        (
            json.dumps({
                "type": "program",
                "id": "1234",
                "data": {"code": {"": {"a": {"b": "c"}}}, "main": {"modulepath": "1", "module": "2", "pipeline": "3"}},
            }),
            "Invalid 'code' parameter given",
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
        "placeholder_query_invalid_data",
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
def test_should_fail_message_validation(websocket_message: str, exception_message: str) -> None:
    mock_connection = MockWebsocketConnection([websocket_message])
    ws_main(mock_connection, app_pipeline_manager)
    assert str(mock_connection.close_message) == exception_message


@pytest.mark.skipif(
    sys.platform.startswith("win") and os.getenv("COVERAGE_RCFILE") is not None,
    reason=(
        "skipping multiprocessing tests on windows if coverage is enabled, as pytest "
        "causes Manager to hang, when using multiprocessing coverage"
    ),
)
@pytest.mark.parametrize(
    argnames="messages,expected_response_runtime_error",
    argvalues=[
        (
            [
                json.dumps({
                    "type": "program",
                    "id": "abcdefgh",
                    "data": {
                        "code": {
                            "": {
                                "gen_test_a": "def pipe():\n\traise Exception('Test Exception')\n",
                                "gen_test_a_pipe": (
                                    "from gen_test_a import pipe\n\nif __name__ == '__main__':\n\tpipe()"
                                ),
                            },
                        },
                        "main": {"modulepath": "", "module": "test_a", "pipeline": "pipe"},
                    },
                }),
            ],
            Message(message_type_runtime_error, "abcdefgh", {"message": "Test Exception"}),
        ),
    ],
    ids=["raise_exception"],
)
def test_should_execute_pipeline_return_exception(
    messages: list[str],
    expected_response_runtime_error: Message,
) -> None:
    mock_connection = MockWebsocketConnection(messages)
    ws_main(mock_connection, app_pipeline_manager)
    mock_connection.wait_for_messages(1)
    exception_message = Message.from_dict(json.loads(mock_connection.received.pop(0)))

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


@pytest.mark.skipif(
    sys.platform.startswith("win") and os.getenv("COVERAGE_RCFILE") is not None,
    reason=(
        "skipping multiprocessing tests on windows if coverage is enabled, as pytest "
        "causes Manager to hang, when using multiprocessing coverage"
    ),
)
@pytest.mark.parametrize(
    argnames="initial_messages,initial_execution_message_wait,appended_messages,expected_responses",
    argvalues=[
        (
            [
                json.dumps({
                    "type": "program",
                    "id": "abcdefg",
                    "data": {
                        "code": {
                            "": {
                                "gen_test_a": (
                                    "import safeds_runner.server.pipeline_manager\n\ndef pipe():\n\tvalue1 ="
                                    " 1\n\tsafeds_runner.server.pipeline_manager.runner_save_placeholder('value1',"
                                    " value1)\n"
                                ),
                                "gen_test_a_pipe": (
                                    "from gen_test_a import pipe\n\nif __name__ == '__main__':\n\tpipe()"
                                ),
                            },
                        },
                        "main": {"modulepath": "", "module": "test_a", "pipeline": "pipe"},
                    },
                }),
            ],
            2,
            [
                # Query Placeholder
                json.dumps({"type": "placeholder_query", "id": "abcdefg", "data": "value1"}),
                # Query invalid placeholder
                json.dumps({"type": "placeholder_query", "id": "abcdefg", "data": "value2"}),
            ],
            [
                # Validate Placeholder Information
                Message(message_type_placeholder_type, "abcdefg", create_placeholder_description("value1", "Int")),
                # Validate Progress Information
                Message(message_type_runtime_progress, "abcdefg", create_runtime_progress_done()),
                # Query Result Valid
                Message(message_type_placeholder_value, "abcdefg", create_placeholder_value("value1", "Int", 1)),
                # Query Result Invalid
                Message(message_type_placeholder_value, "abcdefg", create_placeholder_value("value2", "", "")),
            ],
        ),
    ],
    ids=["query_valid_query_invalid"],
)
def test_should_execute_pipeline_return_valid_placeholder(
    initial_messages: list[str],
    initial_execution_message_wait: int,
    appended_messages: list[str],
    expected_responses: list[Message],
) -> None:
    # Initial execution
    mock_connection = MockWebsocketConnection(initial_messages)
    ws_main(mock_connection, app_pipeline_manager)
    # Wait for at least enough messages to successfully execute pipeline
    mock_connection.wait_for_messages(initial_execution_message_wait)
    # Now send queries
    mock_connection.messages.extend(appended_messages)
    ws_main(mock_connection, app_pipeline_manager)
    # And compare with expected responses
    while len(expected_responses) > 0:
        mock_connection.wait_for_messages(1)
        next_message = Message.from_dict(json.loads(mock_connection.received.pop(0)))
        assert next_message == expected_responses.pop(0)


@pytest.mark.skipif(
    sys.platform.startswith("win") and os.getenv("COVERAGE_RCFILE") is not None,
    reason=(
        "skipping multiprocessing tests on windows if coverage is enabled, as pytest "
        "causes Manager to hang, when using multiprocessing coverage"
    ),
)
@pytest.mark.parametrize(
    argnames="messages,expected_response",
    argvalues=[
        (
            [
                json.dumps({
                    "type": "program",
                    "id": "123456789",
                    "data": {
                        "code": {
                            "": {
                                "gen_b": (
                                    "import safeds_runner.codegen\n"
                                    "from a.stub import u\n"
                                    "from v.u.s.testing import add1\n"
                                    "\n"
                                    "def c():\n"
                                    "\ta1 = 1\n"
                                    "\ta2 = safeds_runner.codegen.eager_or(True, False)\n"
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
                }),
            ],
            Message(message_type_runtime_progress, "123456789", create_runtime_progress_done()),
        ),
        (
            # Query Result Invalid (no pipeline exists)
            [
                json.dumps({"type": "invalid_message_type", "id": "unknown-code-id-never-generated", "data": ""}),
                json.dumps({"type": "placeholder_query", "id": "unknown-code-id-never-generated", "data": "v"}),
            ],
            Message(
                message_type_placeholder_value,
                "unknown-code-id-never-generated",
                create_placeholder_value("v", "", ""),
            ),
        ),
    ],
    ids=["progress_message_done", "invalid_message_invalid_placeholder_query"],
)
def test_should_successfully_execute_simple_flow(messages: list[str], expected_response: Message) -> None:
    mock_connection = MockWebsocketConnection(messages)
    ws_main(mock_connection, app_pipeline_manager)
    mock_connection.wait_for_messages(1)
    query_result_invalid = Message.from_dict(json.loads(mock_connection.received.pop(0)))
    assert query_result_invalid == expected_response
