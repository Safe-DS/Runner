"""Module containing the main entry point, for starting the Safe-DS runner."""

import argparse
import json
import logging
import typing
from typing import Any

import flask.app
import flask_sock
import simple_websocket
from flask import Flask
from flask_cors import CORS
from flask_sock import Sock

from safeds_runner.server import messages
from safeds_runner.server.messages import create_placeholder_value
from safeds_runner.server.pipeline_manager import (
    execute_pipeline,
    get_placeholder,
    set_new_websocket_target,
    setup_pipeline_execution,
)


def create_flask_app(testing: bool = False) -> flask.app.App:
    """
    Create a flask app, that handles all requests.

    :param testing Whether the app should run in a testing context
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

    :param flask_app Flask App
    """
    return Sock(flask_app)


app = create_flask_app()
sock = create_flask_websocket(app)


@sock.route("/WSMain")
def _ws_main(ws: simple_websocket.Server) -> None:
    ws_main(ws)


def ws_main(ws: simple_websocket.Server) -> None:
    """
    Handle websocket requests to the WSMain endpoint.

    This function handles the bidirectional communication between the runner and the vscode-extension.
    :param ws: Websocket Connection, provided by flask
    """
    logging.debug("Request to WSRunProgram")
    set_new_websocket_target(ws)
    while True:
        # This would be a JSON message
        received_message: str = ws.receive()
        if received_message is None:
            logging.debug("Received EOF, closing connection")
            ws.close()
            return
        logging.debug("> Received Message: %s", received_message)
        try:
            received_object: dict[str, Any] = json.loads(received_message)
        except json.JSONDecodeError:
            logging.warning("Invalid message received: %s", received_message)
            ws.close(None, "Invalid Message: not JSON")
            return
        if "type" not in received_object:
            logging.warning("No message type specified in: %s", received_message)
            ws.close(None, "Invalid Message: no type")
            return
        if "id" not in received_object:
            logging.warning("No message id specified in: %s", received_message)
            ws.close(None, "Invalid Message: no id")
            return
        if "data" not in received_object:
            logging.warning("No message data specified in: %s", received_message)
            ws.close(None, "Invalid Message: no data")
            return
        if not isinstance(received_object["type"], str):
            logging.warning("Message type is not a string: %s", received_message)
            ws.close(None, "Invalid Message: invalid type")
            return
        if not isinstance(received_object["id"], str):
            logging.warning("Message id is not a string: %s", received_message)
            ws.close(None, "Invalid Message: invalid id")
            return
        request_data = received_object["data"]
        message_type = received_object["type"]
        execution_id = received_object["id"]
        match message_type:
            case "program":
                valid, invalid_message = messages.validate_program_message(request_data)
                if not valid:
                    logging.warning("Invalid message data specified in: %s (%s)", received_message, invalid_message)
                    ws.close(None, invalid_message)
                    return
                code = request_data["code"]
                msg_main = request_data["main"]
                # This should only be called from the extension as it is a security risk
                execute_pipeline(code, msg_main["package"], msg_main["module"], msg_main["pipeline"], execution_id)
            case "placeholder_query":
                valid, invalid_message = messages.validate_placeholder_query_message(request_data)
                if not valid:
                    logging.warning("Invalid message data specified in: %s (%s)", received_message, invalid_message)
                    ws.close(None, invalid_message)
                    return
                placeholder_type, placeholder_value = get_placeholder(execution_id, request_data)
                if placeholder_type is not None:
                    send_websocket_value(ws, execution_id, request_data, placeholder_type, placeholder_value)
                else:
                    # Send back empty type / value, to communicate that no placeholder exists (yet)
                    # Use name from query to allow linking a response to a request on the peer
                    send_websocket_value(ws, execution_id, request_data, "", "")
            case _:
                if message_type not in messages.message_types:
                    logging.warning("Invalid message type: %s", message_type)


def send_websocket_value(
    connection: simple_websocket.Server,
    exec_id: str,
    name: str,
    var_type: str,
    value: typing.Any,
) -> None:
    """
    Send a computed placeholder value to the vscode-extension.

    :param connection: Websocket connection
    :param exec_id: ID of the execution, where the placeholder to be sent was generated
    :param name: Name of placeholder
    :param var_type: Type of placeholder
    :param value: Value of placeholder
    """
    send_websocket_message(connection, "value", exec_id, create_placeholder_value(name, var_type, value))


def send_websocket_message(
    connection: simple_websocket.Server,
    msg_type: str,
    exec_id: str,
    msg_data: typing.Any,
) -> None:
    """
    Send any message to the vscode-extension.

    :param connection: Websocket connection
    :param msg_type: Message Type
    :param exec_id: ID of the execution, where this message belongs to
    :param msg_data: Message Data
    """
    message = {"type": msg_type, "id": exec_id, "data": msg_data}
    connection.send(json.dumps(message))


def main() -> None:
    """
    Execute the runner application.

    Main entry point of the runner application.
    """
    # Allow prints to be unbuffered by default
    import builtins
    import functools

    builtins.print = functools.partial(print, flush=True)  # type: ignore[assignment]

    logging.getLogger().setLevel(logging.DEBUG)
    from gevent.pywsgi import WSGIServer

    parser = argparse.ArgumentParser(description="Start Safe-DS Runner on a specific port.")
    parser.add_argument("--port", type=int, default=5000, help="Port on which to run the python server.")
    args = parser.parse_args()
    setup_pipeline_execution()
    logging.info("Starting Safe-DS Runner on port %s", str(args.port))
    # Only bind to host=127.0.0.1. Connections from other devices should not be accepted
    WSGIServer(("127.0.0.1", args.port), app).serve_forever()


if __name__ == "__main__":
    main()
