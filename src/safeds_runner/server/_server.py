"""Module containing the server, endpoints and utility functions."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import TYPE_CHECKING

import hypercorn.asyncio
import quart.app
from pydantic import ValidationError

from ._json_encoder import SafeDsEncoder
from ._messages import (
    Message,
    ProgramMessageData,
    QueryMessageData,
    create_placeholder_value,
    message_type_placeholder_value,
    message_types,
    parse_validate_message,
)
from ._pipeline_manager import PipelineManager
from ._process_manager import ProcessManager

if TYPE_CHECKING:
    from collections.abc import Callable


def create_flask_app() -> quart.app.Quart:
    """
    Create a quart app, that handles all requests.

    Returns
    -------
    app:
        App.
    """
    return quart.app.Quart(__name__)


class SafeDsServer:
    """Server containing the flask app, websocket handler and endpoints."""

    def __init__(self) -> None:
        """Create a new server object."""
        self._websocket_target: set[asyncio.Queue] = set()
        self._process_manager = ProcessManager()
        self._pipeline_manager = PipelineManager(self._process_manager)

        self._process_manager.on_message(self.send_message)

        self._app = create_flask_app()
        self._app.config["connect"] = self.connect
        self._app.config["disconnect"] = self.disconnect
        self._app.config["process_manager"] = self._process_manager
        self._app.config["pipeline_manager"] = self._pipeline_manager
        self._app.websocket("/WSMain")(SafeDsServer.ws_main)

    def startup(self, port: int) -> None:
        """
        Listen on the specified port for incoming connections to the runner.

        Parameters
        ----------
        port:
            Port to listen on
        """
        self._process_manager.startup()
        logging.info("Starting Safe-DS Runner on port %s", str(port))
        serve_config = hypercorn.config.Config()
        # Only bind to host=127.0.0.1. Connections from other devices should not be accepted
        serve_config.bind = f"127.0.0.1:{port}"
        serve_config.websocket_ping_interval = 25.0
        event_loop = asyncio.get_event_loop()
        event_loop.run_until_complete(hypercorn.asyncio.serve(self._app, serve_config))
        event_loop.run_forever()  # pragma: no cover

    def shutdown(self) -> None:
        """Shutdown the server."""
        self._process_manager.shutdown()

    def connect(self, websocket_connection_queue: asyncio.Queue) -> None:
        """
        Add a websocket connection queue to relay event messages to, which are occurring during pipeline execution.

        Parameters
        ----------
        websocket_connection_queue:
            Message Queue for a websocket connection.
        """
        self._websocket_target.add(websocket_connection_queue)

    def disconnect(self, websocket_connection_queue: asyncio.Queue) -> None:
        """
        Remove a websocket target connection queue to no longer receive messages.

        Parameters
        ----------
        websocket_connection_queue:
            Message Queue for a websocket connection to be removed.
        """
        if websocket_connection_queue in self._websocket_target:
            self._websocket_target.remove(websocket_connection_queue)

    async def send_message(self, message: Message) -> None:
        """
        Send a message to all connected websocket clients.

        Parameters
        ----------
        message:
            Message to be sent.
        """
        message_encoded = json.dumps(message.to_dict())
        for connection in self._websocket_target:
            await connection.put(message_encoded)

    @staticmethod
    async def ws_main() -> None:
        """Handle websocket requests to the WSMain endpoint and delegates with the required objects."""
        await SafeDsServer._ws_main(
            quart.websocket,
            quart.current_app.config["connect"],
            quart.current_app.config["disconnect"],
            quart.current_app.config["process_manager"],
            quart.current_app.config["pipeline_manager"],
        )

    @staticmethod
    async def _ws_main(
        ws: quart.Websocket,
        connect: Callable,
        disconnect: Callable,
        process_manager: ProcessManager,
        pipeline_manager: PipelineManager,
    ) -> None:
        """
        Handle websocket requests to the WSMain endpoint.

        This function handles the bidirectional communication between the runner and the VS Code extension.

        Parameters
        ----------
        ws:
            Connection
        pipeline_manager:
            Pipeline Manager
        """
        logging.debug("Request to WSRunProgram")
        output_queue: asyncio.Queue = asyncio.Queue()
        connect(output_queue)
        foreground_handler = asyncio.create_task(
            SafeDsServer._ws_main_foreground(ws, disconnect, process_manager, pipeline_manager, output_queue),
        )
        background_handler = asyncio.create_task(
            SafeDsServer._ws_main_background(ws, output_queue),
        )
        await asyncio.gather(foreground_handler, background_handler)

    @staticmethod
    async def _ws_main_foreground(
        ws: quart.Websocket,
        disconnect: Callable,
        process_manager: ProcessManager,
        pipeline_manager: PipelineManager,
        output_queue: asyncio.Queue,
    ) -> None:
        while True:
            # This would be a JSON message
            received_message: str = await ws.receive()
            logging.debug("Received Message: %s", received_message)
            received_object, error_detail, error_short = parse_validate_message(received_message)
            if received_object is None:
                logging.error(error_detail)
                await output_queue.put(None)
                disconnect(output_queue)
                await ws.close(code=1000, reason=error_short)
                return
            match received_object.type:
                case "shutdown":
                    logging.debug("Requested shutdown...")
                    process_manager.shutdown()
                    sys.exit(0)
                case "program":
                    try:
                        program_data = ProgramMessageData(**received_object.data)
                    except ValidationError as validation_error:
                        logging.exception("Invalid message data specified in: %s", received_message)
                        await output_queue.put(None)
                        disconnect(output_queue)
                        await ws.close(code=1000, reason=str(validation_error))
                        return

                    # This should only be called from the extension as it is a security risk
                    pipeline_manager.execute_pipeline(program_data, received_object.id)
                case "placeholder_query":
                    # For this query, a response can be directly sent to the requesting connection

                    try:
                        placeholder_query_data = QueryMessageData(**received_object.data)
                    except ValidationError as validation_error:
                        logging.exception("Invalid message data specified in: %s", received_message)
                        await output_queue.put(None)
                        disconnect(output_queue)
                        await ws.close(code=1000, reason=str(validation_error))
                        return

                    placeholder_type, placeholder_value = pipeline_manager.get_placeholder(
                        received_object.id,
                        placeholder_query_data.name,
                    )
                    # send back a value message
                    if placeholder_type is not None:
                        try:
                            await send_message(
                                ws,
                                Message(
                                    message_type_placeholder_value,
                                    received_object.id,
                                    create_placeholder_value(
                                        placeholder_query_data,
                                        placeholder_type,
                                        placeholder_value,
                                    ),
                                ),
                            )
                        except TypeError as _encoding_error:
                            # if the value can't be encoded send back that the value exists but is not displayable
                            await send_message(
                                ws,
                                Message(
                                    message_type_placeholder_value,
                                    received_object.id,
                                    create_placeholder_value(
                                        placeholder_query_data,
                                        placeholder_type,
                                        "<Not displayable>",
                                    ),
                                ),
                            )
                    else:
                        # Send back empty type / value, to communicate that no placeholder exists (yet)
                        # Use name from query to allow linking a response to a request on the peer
                        await send_message(
                            ws,
                            Message(
                                message_type_placeholder_value,
                                received_object.id,
                                create_placeholder_value(placeholder_query_data, "", ""),
                            ),
                        )
                case _:
                    if received_object.type not in message_types:
                        logging.warning("Invalid message type: %s", received_object.type)

    @staticmethod
    async def _ws_main_background(ws: quart.Websocket, output_queue: asyncio.Queue) -> None:
        while True:
            encoded_message = await output_queue.get()
            if encoded_message is None:
                return
            await ws.send(encoded_message)


async def send_message(connection: quart.Websocket, message: Message) -> None:
    """
    Send a message to the provided websocket connection (to the VS Code extension).

    Parameters
    ----------
    connection:
        Connection that should receive the message.
    message:
        Object that will be sent.
    """
    message_encoded = json.dumps(message.to_dict(), cls=SafeDsEncoder)
    await connection.send(message_encoded)
