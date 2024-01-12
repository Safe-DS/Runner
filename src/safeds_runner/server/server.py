"""Module containing the server, endpoints and utility functions."""

import json
import logging
import sys

import flask.app
import flask_sock
import simple_websocket
from flask import Flask
from flask_cors import CORS
from flask_sock import Sock

from safeds_runner.server import messages
from safeds_runner.server.json_encoder import SafeDsEncoder
from safeds_runner.server.messages import (
    Message,
    create_placeholder_value,
    message_type_placeholder_value,
    parse_validate_message,
)
from safeds_runner.server.pipeline_manager import PipelineManager


def create_flask_app(testing: bool = False) -> flask.app.App:
    """
    Create a flask app, that handles all requests.

    Parameters
    ----------
    testing : bool
        Whether the app should run in a testing context.

    Returns
    -------
    flask.app.App
        Flask app.
    """
    flask_app = Flask(__name__)
    # Websocket Configuration
    flask_app.config["SOCK_SERVER_OPTIONS"] = {"ping_interval": 25}
    flask_app.config["TESTING"] = testing

    # Allow access from VSCode extension
    CORS(flask_app, resources={r"/*": {"origins": "vscode-webview://*"}})
    return flask_app


def create_flask_websocket(flask_app: flask.app.App) -> flask_sock.Sock:
    """
    Create a flask websocket extension.

    Parameters
    ----------
    flask_app: flask.app.App
        Flask App Instance.

    Returns
    -------
    flask_sock.Sock
        Websocket extension for the provided flask app.
    """
    return Sock(flask_app)


class SafeDsServer:
    """
    Server containing the flask app, websocket handler and endpoints.
    """

    def __init__(self, app_pipeline_manager: PipelineManager) -> None:
        """
        Create a new server object.

        Parameters
        ----------
        app_pipeline_manager : PipelineManager
            Manager responsible for executing pipelines sent to this server.
        """
        self.app_pipeline_manager = app_pipeline_manager
        self.app = create_flask_app()
        self.sock = create_flask_websocket(self.app)
        self.sock.route("/WSMain")(lambda ws: self._ws_main(ws, self.app_pipeline_manager))

    def listen(self, port: int) -> None:
        """
        Listen on the specified port for incoming connections to the runner.

        Parameters
        ----------
        port : int
            Port to listen on
        """
        logging.info("Starting Safe-DS Runner on port %s", str(port))
        # Only bind to host=127.0.0.1. Connections from other devices should not be accepted
        from gevent.pywsgi import WSGIServer
        WSGIServer(("127.0.0.1", port), self.app, spawn=8).serve_forever()

    @staticmethod
    def _ws_main(ws: simple_websocket.Server, pipeline_manager: PipelineManager) -> None:
        """
        Handle websocket requests to the WSMain endpoint.

        This function handles the bidirectional communication between the runner and the VS Code extension.

        Parameters
        ----------
        ws : simple_websocket.Server
            Websocket Connection, provided by flask.
        pipeline_manager : PipelineManager
            Manager used to execute pipelines on, and retrieve placeholders from
        """
        logging.debug("Request to WSRunProgram")
        pipeline_manager.connect(ws)
        while True:
            # This would be a JSON message
            received_message: str = ws.receive()
            if received_message is None:
                logging.debug("Received EOF, closing connection")
                pipeline_manager.disconnect(ws)
                ws.close()
                return
            logging.debug("Received Message: %s", received_message)
            received_object, error_detail, error_short = parse_validate_message(received_message)
            if received_object is None:
                logging.error(error_detail)
                pipeline_manager.disconnect(ws)
                ws.close(message=error_short)
                return
            match received_object.type:
                case "shutdown":
                    logging.debug("Requested shutdown...")
                    pipeline_manager.shutdown()
                    sys.exit(0)
                case "program":
                    program_data, invalid_message = messages.validate_program_message_data(received_object.data)
                    if program_data is None:
                        logging.error("Invalid message data specified in: %s (%s)", received_message, invalid_message)
                        pipeline_manager.disconnect(ws)
                        ws.close(None, invalid_message)
                        return
                    # This should only be called from the extension as it is a security risk
                    pipeline_manager.execute_pipeline(program_data, received_object.id)
                case "placeholder_query":
                    # For this query, a response can be directly sent to the requesting connection
                    placeholder_query_data, invalid_message = messages.validate_placeholder_query_message_data(
                        received_object.data,
                    )
                    if placeholder_query_data is None:
                        logging.error("Invalid message data specified in: %s (%s)", received_message, invalid_message)
                        pipeline_manager.disconnect(ws)
                        ws.close(None, invalid_message)
                        return
                    placeholder_type, placeholder_value = pipeline_manager.get_placeholder(
                        received_object.id,
                        placeholder_query_data,
                    )
                    # send back a value message
                    if placeholder_type is not None:
                        try:
                            broadcast_message(
                                [ws],
                                Message(
                                    message_type_placeholder_value,
                                    received_object.id,
                                    create_placeholder_value(placeholder_query_data, placeholder_type,
                                                             placeholder_value),
                                ),
                            )
                        except TypeError as _encoding_error:
                            # if the value can't be encoded send back that the value exists but is not displayable
                            broadcast_message(
                                [ws],
                                Message(
                                    message_type_placeholder_value,
                                    received_object.id,
                                    create_placeholder_value(placeholder_query_data, placeholder_type,
                                                             "<Not displayable>"),
                                ),
                            )
                    else:
                        # Send back empty type / value, to communicate that no placeholder exists (yet)
                        # Use name from query to allow linking a response to a request on the peer
                        broadcast_message(
                            [ws],
                            Message(
                                message_type_placeholder_value,
                                received_object.id,
                                create_placeholder_value(placeholder_query_data, "", ""),
                            ),
                        )
                case _:
                    if received_object.type not in messages.message_types:
                        logging.warning("Invalid message type: %s", received_object.type)


def broadcast_message(connections: list[simple_websocket.Server], message: Message) -> None:
    """
    Send any message to all the provided connections (to the VS Code extension).

    Parameters
    ----------
    connections : list[simple_websocket.Server]
        List of Websocket connections that should receive the message.
    message : Message
        Object that will be sent.
    """
    message_encoded = json.dumps(message.to_dict(), cls=SafeDsEncoder)
    for connection in connections:
        connection.send(message_encoded)
