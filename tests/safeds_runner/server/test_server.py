from __future__ import annotations

import asyncio
import json
import threading

import pytest
import socketio
from pydantic import ValidationError
from safeds_runner.server._server import SafeDsServer
from safeds_runner.server.messages._from_server import (
    MessageFromServer,
    RuntimeErrorMessagePayload,
    create_runtime_error_message,
)
from safeds_runner.server.messages._to_server import (
    MessageToServer,
    VirtualModule,
    create_run_message,
)

PORT = 17394
URL = f"http://localhost:{PORT}"


@pytest.fixture()
async def _server() -> None:
    # Start the server
    server = SafeDsServer()
    server._sio.eio.start_service_task = False

    def run_server():
        asyncio.run(server.startup(PORT))

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    # Run the actual test
    yield

    # Shutdown the server
    await server.shutdown()


@pytest.fixture()
async def client() -> socketio.AsyncSimpleClient:
    async with socketio.AsyncSimpleClient() as sio:
        await sio.connect(URL, transports=["websocket"])
        yield sio


@pytest.mark.parametrize(
    argnames=("request_", "expected_response"),
    argvalues=[
        (
            create_run_message(
                run_id="raise_exception",
                code=[
                    VirtualModule(
                        absolute_module_name="main",
                        code=(
                            "if __name__ == '__main__':"
                            "    raise Exception('Test Exception')"
                        ),
                    ),
                ],
                main_absolute_module_name="main",
            ),
            create_runtime_error_message(
                run_id="raise_exception",
                message="Test Exception",
                stacktrace=[],
            ),
        ),
    ],
    ids=["runtime_error"],
)
@pytest.mark.usefixtures("_server")
async def test_runtime_error(
    client: socketio.AsyncSimpleClient,
    request_: MessageToServer,
    expected_response: MessageFromServer,
) -> None:
    await client.emit(request_.event, request_.payload.model_dump_json())
    [actual_event, actual_payload] = await client.receive(timeout=50)

    # Event should be correct
    assert actual_event == expected_response.event

    # Payload should have expected structure
    try:
        runtime_error_payload = RuntimeErrorMessagePayload(**json.loads(actual_payload))
    except (TypeError, ValidationError):
        pytest.fail("Invalid response payload")

    # Stacktrace should not be empty
    assert len(runtime_error_payload.stacktrace) > 0
    runtime_error_payload.stacktrace = []

    # Check the rest of the data
    assert runtime_error_payload == expected_response.payload
