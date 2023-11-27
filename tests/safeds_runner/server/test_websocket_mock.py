import threading
import typing

import pytest

from safeds_runner.server.main import ws_main
from safeds_runner.server.pipeline_manager import setup_pipeline_execution
import json


class MockWebsocketConnection:
    def __init__(self, messages: list[str]):
        self.messages = messages
        self.received: list[str] = []
        self.close_reason = None
        self.close_message = None
        self.condition_variable = threading.Condition()

    def send(self, msg: str) -> None:
        self.received.append(msg)
        with self.condition_variable:
            self.condition_variable.notify_all()

    def receive(self) -> str | None:
        if len(self.messages) == 0:
            return None
        return self.messages.pop(0)

    def close(self, reason: int | None = None, message: str | None = None):
        self.close_reason = reason
        self.close_message = message

    def wait_for_messages(self, wait_for_messages: int = 1) -> None:
        while True:
            with self.condition_variable:
                if len(self.received) >= wait_for_messages:
                    return
                self.condition_variable.wait()


def test_websocket_no_json():
    # with pytest.raises(ConnectionResetError) as exception:
    mock_connection = MockWebsocketConnection(["<invalid message>"])
    ws_main(mock_connection)
    assert str(mock_connection.close_message) == "Invalid Message: not JSON"


@pytest.mark.parametrize("websocket_message,exception_message", [
    ({"id": "a", "data": "b"}, "Invalid Message: no type"),
    ({"type": "a", "data": "b"}, "Invalid Message: no id"),
    ({"type": "b", "id": "123"}, "Invalid Message: no data"),
    ({"type": {"program": "2"}, "id": "123", "data": "a"}, "Invalid Message: invalid type"),
    ({"type": "c", "id": {"": "1233"}, "data": "a"}, "Invalid Message: invalid id"),
    ({"type": "program", "id": "1234", "data": "a"}, "Message data is not a JSON object"),
    ({"type": "placeholder_query", "id": "123", "data": {"a": "v"}}, "Message data is not a string"),
    ({"type": "program", "id": "1234", "data": {"main": {"package": "1", "module": "2", "pipeline": "3"}}},
     "No 'code' parameter given"),
    ({"type": "program", "id": "1234", "data": {"code": {"": {"entry": ""}}}}, "No 'main' parameter given"),
    ({"type": "program", "id": "1234", "data": {"code": {"": {"entry": ""}}, "main": {"package": "1", "module": "2"}}},
     "Invalid 'main' parameter given"),
    (
        {"type": "program", "id": "1234",
         "data": {"code": {"": {"entry": ""}}, "main": {"package": "1", "pipeline": "3"}}},
        "Invalid 'main' parameter given"),
    ({"type": "program", "id": "1234", "data": {"code": {"": {"entry": ""}}, "main": {"module": "2", "pipeline": "3"}}},
     "Invalid 'main' parameter given"),
    ({"type": "program", "id": "1234",
      "data": {"code": {"": {"entry": ""}}, "main": {"package": "1", "module": "2", "pipeline": "3", "other": "4"}}},
     "Invalid 'main' parameter given"),
    ({"type": "program", "id": "1234", "data": {"code": {"": {"entry": ""}},
                                                "main": {"package": "1", "module": "2", "pipeline": "3",
                                                         "other": {"4": "a"}}}},
     "Invalid 'main' parameter given"),
    ({"type": "program", "id": "1234", "data": {"code": "a", "main": {"package": "1", "module": "2", "pipeline": "3"}}},
     "Invalid 'code' parameter given"),
    ({"type": "program", "id": "1234",
      "data": {"code": {"": "a"}, "main": {"package": "1", "module": "2", "pipeline": "3"}}},
     "Invalid 'code' parameter given"),
    ({"type": "program", "id": "1234",
      "data": {"code": {"": {"a": {"b": "c"}}}, "main": {"package": "1", "module": "2", "pipeline": "3"}}},
     "Invalid 'code' parameter given"),
], ids=[
    "any_no_type", "any_no_id", "any_no_data", "any_invalid_type", "any_invalid_id", "program_invalid_data",
    "placeholder_query_invalid_data", "program_no_code", "program_no_main", "program_invalid_main1",
    "program_invalid_main2", "program_invalid_main3", "program_invalid_main4",
    "program_invalid_main5", "program_invalid_code1", "program_invalid_code2", "program_invalid_code3"
])
def test_websocket_validation_error(websocket_message: dict[str, typing.Any], exception_message: str):
    # with pytest.raises(ConnectionResetError) as exception:
    mock_connection = MockWebsocketConnection([json.dumps(websocket_message)])
    ws_main(mock_connection)
    assert str(mock_connection.close_message) == exception_message


def test_websocket_progress_message_done():
    setup_pipeline_execution()
    code_id = "123456789"
    code_message = {
        "type": "program", "id": code_id,
        "data":
            {"code": {"": {"gen_b": (
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
                "gen_b_c": "from gen_b import c\n\nif __name__ == '__main__':\n\tc()"},
                "a": {"stub": "def u():\n\treturn 1"},
                "v.u.s": {"testing": "import a.stub;\n\ndef add1(v1, v2):\n\treturn v1 + v2 + a.stub.u()\n"},
            },
                "main": {"package": "", "module": "b", "pipeline": "c"}}}
    mock_connection = MockWebsocketConnection([json.dumps(code_message)])
    ws_main(mock_connection)
    mock_connection.wait_for_messages(1)
    done_message = json.loads(mock_connection.received.pop(0))
    assert done_message["type"] == "progress"
    assert done_message["id"] == code_id
    assert done_message["data"] == "done"


def test_websocket_exception_message():
    setup_pipeline_execution()
    code_id = "abcdefg"
    code_message = {
        "type": "program", "id": code_id,
        "data":
            {"code": {"": {"gen_test_a": (
                "def pipe():\n"
                "\traise Exception('Test Exception')\n"
            ),
                "gen_test_a_pipe": "from gen_test_a import pipe\n\nif __name__ == '__main__':\n\tpipe()"},
            },
                "main": {"package": "", "module": "test_a", "pipeline": "pipe"}}}
    mock_connection = MockWebsocketConnection([json.dumps(code_message)])
    ws_main(mock_connection)
    mock_connection.wait_for_messages(1)
    exception_message = json.loads(mock_connection.received.pop(0))
    assert exception_message["type"] == "runtime_error"
    assert exception_message["id"] == code_id
    assert isinstance(exception_message["data"], dict)
    assert exception_message["data"]["message"] == "Test Exception"
    assert isinstance(exception_message["data"]["backtrace"], list)
    assert len(exception_message["data"]["backtrace"]) > 0
    for frame in exception_message["data"]["backtrace"]:
        assert "file" in frame and isinstance(frame["file"], str)
        assert "line" in frame and isinstance(frame["line"], int)


def test_websocket_placeholder_valid():
    setup_pipeline_execution()
    code_id = "abcdefg"
    code_message = {
        "type": "program", "id": code_id,
        "data":
            {"code": {"": {"gen_test_a": (
                "import safeds_runner.server.pipeline_manager\n\n"
                "def pipe():\n"
                "\tvalue1 = 1\n"
                "\tsafeds_runner.server.pipeline_manager.runner_save_placeholder('value1', value1)\n"
            ),
                "gen_test_a_pipe": "from gen_test_a import pipe\n\nif __name__ == '__main__':\n\tpipe()"},
            },
                "main": {"package": "", "module": "test_a", "pipeline": "pipe"}}}
    mock_connection = MockWebsocketConnection([json.dumps(code_message)])
    ws_main(mock_connection)
    mock_connection.wait_for_messages(2)
    placeholder_type_message = json.loads(mock_connection.received.pop(0))
    # Validate Placeholder Information
    assert placeholder_type_message["type"] == "placeholder_type"
    assert placeholder_type_message["id"] == code_id
    assert isinstance(placeholder_type_message["data"], dict)
    assert "name" in placeholder_type_message["data"]
    assert "type" in placeholder_type_message["data"]
    assert placeholder_type_message["data"]["name"] == "value1"
    assert placeholder_type_message["data"]["type"] == "Int"
    # Validate Progress Information
    done_message = json.loads(mock_connection.received.pop(0))
    assert done_message["type"] == "progress"
    assert done_message["id"] == code_id
    assert done_message["data"] == "done"
    # Query Placeholder
    mock_connection.messages.append(json.dumps({"type": "placeholder_query", "id": code_id, "data": "value1"}))
    ws_main(mock_connection)
    mock_connection.wait_for_messages(1)
    # Query Result Valid
    query_result = json.loads(mock_connection.received.pop(0))
    assert query_result["type"] == "value"
    assert query_result["id"] == code_id
    assert isinstance(query_result["data"], dict)
    assert "name" in query_result["data"]
    assert "type" in query_result["data"]
    assert "value" in query_result["data"]
    assert query_result["data"]["name"] == "value1"
    assert query_result["data"]["type"] == "Int"
    assert query_result["data"]["value"] == 1
    # Query invalid placeholder
    invalid_name_placeholder = "value2"
    mock_connection.messages.append(
        json.dumps({"type": "placeholder_query", "id": code_id, "data": invalid_name_placeholder}))
    ws_main(mock_connection)
    mock_connection.wait_for_messages(1)
    # Query Result Invalid
    query_result_invalid = json.loads(mock_connection.received.pop(0))
    assert query_result_invalid["type"] == "value"
    assert query_result_invalid["id"] == code_id
    assert isinstance(query_result_invalid["data"], dict)
    assert "name" in query_result_invalid["data"]
    assert "type" in query_result_invalid["data"]
    assert "value" in query_result_invalid["data"]
    assert query_result_invalid["data"]["name"] == invalid_name_placeholder
    # invalid queries respond with an empty type and empty value
    assert query_result_invalid["data"]["type"] == ""
    assert query_result_invalid["data"]["value"] == ""


def test_websocket_invalid_message_invalid_placeholder_query():
    setup_pipeline_execution()
    code_id = "unknown-code-id-never-generated"
    placeholder_name = "v"
    mock_connection = MockWebsocketConnection([
        json.dumps({"type": "invalid_message_type", "id": code_id, "data": ""}),
        json.dumps({"type": "placeholder_query", "id": code_id, "data": placeholder_name})
    ])
    ws_main(mock_connection)
    mock_connection.wait_for_messages(1)
    # Query Result Invalid (no pipeline exists)
    query_result_invalid = json.loads(mock_connection.received.pop(0))
    assert query_result_invalid["type"] == "value"
    assert query_result_invalid["id"] == code_id
    assert isinstance(query_result_invalid["data"], dict)
    assert "name" in query_result_invalid["data"]
    assert "type" in query_result_invalid["data"]
    assert "value" in query_result_invalid["data"]
    assert query_result_invalid["data"]["name"] == placeholder_name
    # invalid queries respond with an empty type and empty value
    assert query_result_invalid["data"]["type"] == ""
    assert query_result_invalid["data"]["value"] == ""
