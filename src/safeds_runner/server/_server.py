"""Module containing the server, endpoints and utility functions."""

import asyncio
import json
import logging
import sys

import hypercorn.asyncio
import quart.app

from ._json_encoder import SafeDsEncoder
from ._messages import (
    Message,
    create_placeholder_value,
    message_type_placeholder_value,
    message_types,
    parse_validate_message,
    validate_placeholder_query_message_data,
    validate_program_message_data,
)
from ._pipeline_manager import PipelineManager


def create_flask_app() -> quart.app.Quart:
    """
    Create a quart app, that handles all requests.

    Returns
    -------
    quart.app.Quart
        App.
    """
    return quart.app.Quart(__name__)


class SafeDsServer:
    """Server containing the flask app, websocket handler and endpoints."""

    def __init__(self) -> None:
        """Create a new server object."""
        self.app_pipeline_manager = PipelineManager()
        self.app = create_flask_app()
        self.app.config["pipeline_manager"] = self.app_pipeline_manager
        self.app.websocket("/WSMain")(SafeDsServer.ws_main)

    def listen(self, port: int) -> None:
        """
        Listen on the specified port for incoming connections to the runner.

        Parameters
        ----------
        port : int
            Port to listen on
        """
        logging.info("Starting Safe-DS Runner on port %s", str(port))
        serve_config = hypercorn.config.Config()
        # Only bind to host=127.0.0.1. Connections from other devices should not be accepted
        serve_config.bind = f"127.0.0.1:{port}"
        serve_config.websocket_ping_interval = 25.0
        event_loop = asyncio.get_event_loop()
        event_loop.run_until_complete(hypercorn.asyncio.serve(self.app, serve_config))
        event_loop.run_forever()  # pragma: no cover

    @staticmethod
    async def ws_main() -> None:
        """Handle websocket requests to the WSMain endpoint and delegates with the required objects."""
        await SafeDsServer._ws_main(quart.websocket, quart.current_app.config["pipeline_manager"])

    @staticmethod
    async def _ws_main(ws: quart.Websocket, pipeline_manager: PipelineManager) -> None:
        """
        Handle websocket requests to the WSMain endpoint.

        This function handles the bidirectional communication between the runner and the VS Code extension.

        Parameters
        ----------
        ws : quart.Websocket
            Connection
        pipeline_manager : PipelineManager
            Pipeline Manager
        """
        logging.debug("Request to WSRunProgram")
        output_queue: asyncio.Queue = asyncio.Queue()
        pipeline_manager.connect(output_queue)
        foreground_handler = asyncio.create_task(SafeDsServer._ws_main_foreground(ws, pipeline_manager, output_queue))
        background_handler = asyncio.create_task(SafeDsServer._ws_main_background(ws, output_queue))
        await asyncio.gather(foreground_handler, background_handler)

    @staticmethod
    async def _ws_main_foreground(
        ws: quart.Websocket,
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
                pipeline_manager.disconnect(output_queue)
                await ws.close(code=1000, reason=error_short)
                return
            match received_object.type:
                case "shutdown":
                    logging.debug("Requested shutdown...")
                    pipeline_manager.shutdown()
                    sys.exit(0)
                case "program":
                    program_data, invalid_message = validate_program_message_data(received_object.data)
                    if program_data is None:
                        logging.error("Invalid message data specified in: %s (%s)", received_message, invalid_message)
                        await output_queue.put(None)
                        pipeline_manager.disconnect(output_queue)
                        await ws.close(code=1000, reason=invalid_message)
                        return
                    # This should only be called from the extension as it is a security risk
                    pipeline_manager.execute_pipeline(program_data, received_object.id)
                case "placeholder_query":
                    # For this query, a response can be directly sent to the requesting connection
                    placeholder_query_data, invalid_message = validate_placeholder_query_message_data(
                        received_object.data,
                    )
                    if placeholder_query_data is None:
                        logging.error("Invalid message data specified in: %s (%s)", received_message, invalid_message)
                        await output_queue.put(None)
                        pipeline_manager.disconnect(output_queue)
                        await ws.close(code=1000, reason=invalid_message)
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
    connection : quart.Websocket
        Connection that should receive the message.
    message : Message
        Object that will be sent.
    """
    message_encoded = json.dumps(message.to_dict(), cls=SafeDsEncoder)
    await connection.send(message_encoded)
