from __future__ import annotations

import asyncio
import itertools
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
    create_done_message,
    create_progress_message,
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
async def client_1() -> socketio.AsyncSimpleClient:
    async with socketio.AsyncSimpleClient() as sio:
        await sio.connect(URL, wait_timeout=BASE_TIMEOUT)
        yield sio


@pytest.fixture()
async def client_2() -> socketio.AsyncSimpleClient:
    async with socketio.AsyncSimpleClient() as sio:
        await sio.connect(URL, wait_timeout=BASE_TIMEOUT)
        yield sio


# Normal flow ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    argnames=("correspondence_client_1", "correspondence_client_2"),
    argvalues=[
        (  # simple
            [
                create_run_message(
                    run_id="simple",
                    code=[
                        VirtualModule(
                            absolute_module_name="main",
                            code=(
                                "if __name__ == '__main__':\n"
                                "    print('Hello, World!')\n"
                            ),
                        ),
                    ],
                    main_absolute_module_name="main",
                ),
                create_done_message(run_id="simple"),
            ],
            [],
        ),
        (  # simple_two_clients
            [
                create_run_message(
                    run_id="simple_two_clients_1",
                    code=[
                        VirtualModule(
                            absolute_module_name="main",
                            code=(
                                "if __name__ == '__main__':\n"
                                "    print('Hello, World!')\n"
                            ),
                        ),
                    ],
                    main_absolute_module_name="main",
                ),
                create_done_message(run_id="simple_two_clients_1"),
            ],
            [
                create_run_message(
                    run_id="simple_two_clients_2",
                    code=[
                        VirtualModule(
                            absolute_module_name="main",
                            code=(
                                "if __name__ == '__main__':\n"
                                "    print('Hello, World!')\n"
                            ),
                        ),
                    ],
                    main_absolute_module_name="main",
                ),
                create_done_message(run_id="simple_two_clients_2"),
            ],
        ),
        (  # multiple_modules_import
            [
                create_run_message(
                    run_id="multiple_modules_import",
                    code=[
                        VirtualModule(
                            absolute_module_name="module_1",
                            code=(
                                "def hello_world():\n"
                                "    return 'Hello, World!'\n"
                            ),
                        ),
                        VirtualModule(
                            absolute_module_name="main",
                            code=(
                                "import module_1\n"
                                "if __name__ == '__main__':\n"
                                "    print(module_1.hello_world())\n"
                            ),
                        ),
                    ],
                    main_absolute_module_name="main",
                ),
                create_done_message(run_id="multiple_modules_import"),
            ],
            [],
        ),
        (  # multiple_modules_from_import
            [
                create_run_message(
                    run_id="multiple_modules_from_import",
                    code=[
                        VirtualModule(
                            absolute_module_name="module_1",
                            code=(
                                "def hello_world():\n"
                                "    return 'Hello, World!'\n"
                            ),
                        ),
                        VirtualModule(
                            absolute_module_name="main",
                            code=(
                                "from module_1 import hello_world\n"
                                "if __name__ == '__main__':\n"
                                "    print(hello_world())\n"
                            ),
                        ),
                    ],
                    main_absolute_module_name="main",
                ),
                create_done_message(run_id="multiple_modules_from_import"),
            ],
            [],
        ),
        (  # report_placeholder_computed
            [
                create_run_message(
                    run_id="report_placeholder_computed",
                    code=[
                        VirtualModule(
                            absolute_module_name="main",
                            code=(
                                "import safeds_runner\n"
                                "if __name__ == '__main__':\n"
                                "    safeds_runner.report_placeholder_computed('test')\n"
                            ),
                        ),
                    ],
                    main_absolute_module_name="main",
                ),
                create_progress_message(
                    run_id="report_placeholder_computed",
                    placeholder_name="test",
                    percentage=100,
                ),
                create_done_message(run_id="report_placeholder_computed"),
            ],
            [],
        ),
        (  # report_placeholder_computed_multiple_placeholders
            [
                create_run_message(
                    run_id="report_placeholder_computed_multiple_placeholders",
                    code=[
                        VirtualModule(
                            absolute_module_name="main",
                            code=(
                                "import safeds_runner\n"
                                "if __name__ == '__main__':\n"
                                "    safeds_runner.report_placeholder_computed('test_1')\n"
                                "    safeds_runner.report_placeholder_computed('test_2')\n"
                            ),
                        ),
                    ],
                    main_absolute_module_name="main",
                ),
                create_progress_message(
                    run_id="report_placeholder_computed_multiple_placeholders",
                    placeholder_name="test_1",
                    percentage=100,
                ),
                create_progress_message(
                    run_id="report_placeholder_computed_multiple_placeholders",
                    placeholder_name="test_2",
                    percentage=100,
                ),
                create_done_message(run_id="report_placeholder_computed_multiple_placeholders"),
            ],
            [],
        ),
        (  # report_placeholder_computed_two_clients
            [
                create_run_message(
                    run_id="report_placeholder_computed_two_clients_1",
                    code=[
                        VirtualModule(
                            absolute_module_name="main",
                            code=(
                                "import safeds_runner\n"
                                "if __name__ == '__main__':\n"
                                "    safeds_runner.report_placeholder_computed('test_1')\n"
                            ),
                        ),
                    ],
                    main_absolute_module_name="main",
                ),
                create_progress_message(
                    run_id="report_placeholder_computed_two_clients_1",
                    placeholder_name="test_1",
                    percentage=100,
                ),
                create_done_message(run_id="report_placeholder_computed_two_clients_1"),
            ],
            [
                create_run_message(
                    run_id="report_placeholder_computed_two_clients_2",
                    code=[
                        VirtualModule(
                            absolute_module_name="main",
                            code=(
                                "import safeds_runner\n"
                                "if __name__ == '__main__':\n"
                                "    safeds_runner.report_placeholder_computed('test_2')\n"
                            ),
                        ),
                    ],
                    main_absolute_module_name="main",
                ),
                create_progress_message(
                    run_id="report_placeholder_computed_two_clients_2",
                    placeholder_name="test_2",
                    percentage=100,
                ),
                create_done_message(run_id="report_placeholder_computed_two_clients_2"),
            ],
        ),
    ],
    ids=[
        "simple",
        "simple_two_clients",
        "multiple_modules_import",
        "multiple_modules_from_import",
        "report_placeholder_computed",
        "report_placeholder_computed_multiple_placeholders",
        "report_placeholder_computed_two_clients",
    ],
)
@pytest.mark.usefixtures("_server")
async def test_normal_flow(
    client_1: socketio.AsyncSimpleClient,
    client_2: socketio.AsyncSimpleClient,
    correspondence_client_1: list[MessageToServer | MessageFromServer],
    correspondence_client_2: list[MessageToServer | MessageFromServer],
) -> None:
    # Send and receive messages with both clients
    for message_1, message_2 in itertools.zip_longest(correspondence_client_1, correspondence_client_2):
        await _send_or_receive(message_1, client_1)
        await _send_or_receive(message_2, client_2)


async def _send_or_receive(message: MessageToServer | MessageFromServer | None, client: socketio.AsyncSimpleClient):
    if isinstance(message, MessageToServer):
        await client.emit(message.event, message.payload.model_dump_json())
    elif isinstance(message, MessageFromServer):
        [actual_event, actual_payload] = await client.receive(timeout=BASE_TIMEOUT)

        # Event should be correct
        assert actual_event == message.event

        # Payload should be correct
        assert actual_payload == message.payload.model_dump_json()


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
    client_1: socketio.AsyncSimpleClient,
    request_: MessageToServer,
    expected_response: MessageFromServer,
) -> None:
    await client_1.emit(request_.event, request_.payload.model_dump_json())
    [actual_event, actual_payload] = await client_1.receive(timeout=BASE_TIMEOUT)

    # Event should be correct
    assert actual_event == expected_response.event

    # Payload should have expected structure
    try:
        runtime_warning_payload = RuntimeWarningMessagePayload(**json.loads(actual_payload))
    except (TypeError, ValidationError):
        pytest.fail("Invalid response payload.")

    # Stacktrace should not be empty
    assert len(runtime_warning_payload.stacktrace) > 0

    # Rest of the data should be correct
    runtime_warning_payload.stacktrace = []
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
    client_1: socketio.AsyncSimpleClient,
    request_: MessageToServer,
    expected_response: MessageFromServer,
) -> None:
    await client_1.emit(request_.event, request_.payload.model_dump_json())
    [actual_event, actual_payload] = await client_1.receive(timeout=BASE_TIMEOUT)

    # Event should be correct
    assert actual_event == expected_response.event

    # Payload should have expected structure
    try:
        runtime_error_payload = RuntimeErrorMessagePayload(**json.loads(actual_payload))
    except (TypeError, ValidationError):
        pytest.fail("Invalid response payload.")

    # Stacktrace should not be empty
    assert len(runtime_error_payload.stacktrace) > 0

    # Rest of the data should be correct
    runtime_error_payload.stacktrace = []
    assert runtime_error_payload == expected_response.payload


# Test shutdown --------------------------------------------------------------------------------------------------------

SHUTDOWN_PORT = PORT + 1
SHUTDOWN_URL = f"http://localhost:{SHUTDOWN_PORT}"


async def test_shutdown() -> None:
    # Start the server that should be shut down
    process = multiprocessing.Process(target=run_server_to_shutdown)
    process.start()

    try:
        # Send a shutdown message
        async with socketio.AsyncSimpleClient() as client_:
            await client_.connect(SHUTDOWN_URL, wait_timeout=BASE_TIMEOUT)
            await client_.emit(create_shutdown_message().event)

            # Joining on the process can lead to a loss of the shutdown message
            for _ in range(10 * BASE_TIMEOUT):
                if not process.is_alive():
                    break
                await asyncio.sleep(0.1)
    finally:
        # Kill the process and all child processes if it did not shut down in time
        if process.is_alive():
            parent = psutil.Process(process.pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
            pytest.fail("Server did not shut down in time.")

    # Check the exit code
    assert process.exitcode == 0


def run_server_to_shutdown():
    server = SafeDsServer()
    server._sio.eio.start_service_task = False
    asyncio.run(server.startup(SHUTDOWN_PORT))
