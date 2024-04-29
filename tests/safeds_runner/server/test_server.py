from __future__ import annotations

import asyncio
import json
import multiprocessing
import threading

import psutil
import pytest
import socketio
from pydantic import ValidationError
from safeds_runner.server._server import SafeDsServer
from safeds_runner.server.messages._from_server import (
    MessageFromServer,
    RuntimeErrorMessagePayload,
    RuntimeWarningMessagePayload,
    create_runtime_error_message,
    create_runtime_warning_message,
)
from safeds_runner.server.messages._to_server import (
    MessageToServer,
    VirtualModule,
    create_run_message,
    create_shutdown_message,
)

BASE_TIMEOUT = 10
PORT = 17394
URL = f"http://localhost:{PORT}"


@pytest.fixture(scope="module")
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


# Test runtime warning -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    argnames=("request_", "expected_response"),
    argvalues=[
        (
            create_run_message(
                run_id="runtime_warning",
                code=[
                    VirtualModule(
                        absolute_module_name="main",
                        code=(
                            "import warnings\n"
                            "if __name__ == '__main__':\n"
                            "    warnings.warn('Test Warning')"
                        ),
                    ),
                ],
                main_absolute_module_name="main",
            ),
            create_runtime_warning_message(
                run_id="runtime_warning",
                message="Test Warning",
                stacktrace=[],
            ),
        ),
    ],
    ids=["runtime_warning"],
)
@pytest.mark.usefixtures("_server")
async def test_runtime_warning(
    client: socketio.AsyncSimpleClient,
    request_: MessageToServer,
    expected_response: MessageFromServer,
) -> None:
    await client.emit(request_.event, request_.payload.model_dump_json())
    [actual_event, actual_payload] = await client.receive(timeout=BASE_TIMEOUT)

    # Event should be correct
    assert actual_event == expected_response.event

    # Payload should have expected structure
    try:
        runtime_warning_payload = RuntimeWarningMessagePayload(**json.loads(actual_payload))
    except (TypeError, ValidationError):
        pytest.fail("Invalid response payload.")

    # Stacktrace should not be empty
    assert len(runtime_warning_payload.stacktrace) > 0
    runtime_warning_payload.stacktrace = []

    # Check the rest of the data
    assert runtime_warning_payload == expected_response.payload


# Test runtime_error ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    argnames=("request_", "expected_response"),
    argvalues=[
        (
            create_run_message(
                run_id="runtime_error",
                code=[
                    VirtualModule(
                        absolute_module_name="main",
                        code=(
                            "if __name__ == '__main__':\n"
                            "    raise Exception('Test Exception')\n"
                        ),
                    ),
                ],
                main_absolute_module_name="main",
            ),
            create_runtime_error_message(
                run_id="runtime_error",
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
    [actual_event, actual_payload] = await client.receive(timeout=BASE_TIMEOUT)

    # Event should be correct
    assert actual_event == expected_response.event

    # Payload should have expected structure
    try:
        runtime_error_payload = RuntimeErrorMessagePayload(**json.loads(actual_payload))
    except (TypeError, ValidationError):
        pytest.fail("Invalid response payload.")

    # Stacktrace should not be empty
    assert len(runtime_error_payload.stacktrace) > 0
    runtime_error_payload.stacktrace = []

    # Check the rest of the data
    assert runtime_error_payload == expected_response.payload


# Test shutdown --------------------------------------------------------------------------------------------------------

SHUTDOWN_PORT = PORT + 1
SHUTDOWN_URL = f"http://localhost:{SHUTDOWN_PORT}"


def test_shutdown() -> None:
    process = multiprocessing.Process(target=sync_run_shutdown_server)
    process.start()
    process.join(3 * BASE_TIMEOUT)

    # Kill the server if it did not shut down in time
    if process.is_alive():
        parent = psutil.Process(process.pid)
        for child in parent.children(recursive=True):
            child.kill()
        pytest.fail("Server did not shut down in time.")

    assert process.exitcode == 0


def sync_run_shutdown_server():
    asyncio.run(run_shutdown_server())


async def run_shutdown_server():
    # Start the server
    server = SafeDsServer()
    server._sio.eio.start_service_task = False

    def run_server():
        asyncio.run(server.startup(SHUTDOWN_PORT))

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    # Connect with a client and send a shutdown message
    async with socketio.AsyncSimpleClient() as shutdown_client:
        await shutdown_client.connect(SHUTDOWN_URL, transports=["websocket"])
        await shutdown_client.emit(create_shutdown_message().event)
