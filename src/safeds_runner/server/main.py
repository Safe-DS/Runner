"""Module containing the main entry point, for starting the Safe-DS runner"""
import argparse

import json
import logging
import typing
from typing import Any

import simple_websocket
from flask import Flask
from flask_cors import CORS
from flask_sock import Sock

from safeds_runner.server import messages
from safeds_runner.server.pipeline_manager import execute_pipeline, get_placeholder, set_new_websocket_target, \
    setup_pipeline_execution

app = Flask(__name__)
# Websocket Configuration
app.config['SOCK_SERVER_OPTIONS'] = {'ping_interval': 25}
sock = Sock(app)
# Allow access from VSCode extension
CORS(app, resources={r"/*": {"origins": "vscode-webview://*"}})

"""
Args should contain every source file that was generated
code: ["<package>" => ["<file>" => "<code>", ...], ...]
main: {"package": <package; Value of Package directive on Safe-DS module>, "module": <module; Name of Safe-DS source file>, "pipeline": <pipeline; Name of executable Pipeline>}
:return: Tuple: (Result String, HTTP Code)
"""


@sock.route("/WSMain")
def ws_run_program(ws: simple_websocket.Server) -> None:
    """
    Handles websocket requests to the WSMain endpoint.

    This function handles the bidirectional communication between the runner and the vscode-extension.
    :param ws: Websocket Connection, provided by flask
    """
    logging.debug("Request to WSRunProgram")
    set_new_websocket_target(ws)
    while True:
        # This would be a JSON message
        received_message: str = ws.receive()
        logging.debug("> Received Message: %s", received_message)
        try:
            received_object: dict[str, Any] = json.loads(received_message)
        except json.JSONDecodeError:
            logging.warn("Invalid message received: %s", received_message)
            ws.close(None)
            return
        if "type" not in received_object:
            logging.warn("No message type specified in: %s", received_message)
            ws.close(None)
            return
        if "id" not in received_object:
            logging.warn("No message id specified in: %s", received_message)
            ws.close(None)
            return
        if "data" not in received_object:
            logging.warn("No message data specified in: %s", received_message)
            ws.close(None)
            return
        if not isinstance(received_object["type"], str):
            logging.warn("Message type is not a string: %s", received_message)
            ws.close(None)
            return
        if not isinstance(received_object["id"], str):
            logging.warn("Message id is not a string: %s", received_message)
            ws.close(None)
            return
        request_data = received_object["data"]
        message_type = received_object["type"]
        execution_id = received_object["id"]
        match message_type:
            case "program":
                valid, invalid_message = messages.validate_program_message(request_data)
                if not valid:
                    logging.warn("Invalid message data specified in: %s (%s)", received_message, invalid_message)
                    ws.close(None)
                    return
                code = request_data["code"]
                main = request_data["main"]
                # This should only be called from the extension as it is a security risk
                execute_pipeline(code, main['package'], main['module'], main['pipeline'], execution_id)
            case "placeholder_query":
                valid, invalid_message = messages.validate_placeholder_query_message(request_data)
                if not valid:
                    logging.warn("Invalid message data specified in: %s (%s)", received_message, invalid_message)
                    ws.close(None)
                    return
                placeholder_type, placeholder_value = get_placeholder(execution_id, request_data)
                if placeholder_type is not None:
                    send_websocket_value(ws, request_data, placeholder_type, placeholder_value)
                else:
                    # Send back empty type / value, to communicate that no placeholder exists (yet)
                    send_websocket_value(ws, request_data, "", "")
            case _:
                if message_type not in messages.message_types:
                    logging.warn("Invalid message type: %s", message_type)


def send_websocket_value(connection: simple_websocket.Server, name: str, var_type: str, value: str) -> None:
    """
    Send a computed placeholder value to the vscode-extension.

    :param connection: Websocket connection
    :param name: Name of placeholder
    :param var_type: Type of placeholder
    :param value: Value of placeholder
    """
    send_websocket_message(connection, "value", {"name": name, "type": var_type, "value": value})


def send_websocket_message(connection: simple_websocket.Server, msg_type: str, msg_data: typing.Any) -> None:
    """
    Send any message to the vscode-extension.

    :param connection: Websocket connection
    :param msg_type: Message Type
    :param msg_data: Message Data
    """
    message = {"type": msg_type, "data": msg_data}
    connection.send(json.dumps(message))


if __name__ == "__main__":
    # Allow prints to be unbuffered by default
    import functools
    import builtins

    builtins.print = functools.partial(print, flush=True)  # type: ignore[assignment]

    logging.getLogger().setLevel(logging.DEBUG)
    from gevent.pywsgi import WSGIServer

    parser = argparse.ArgumentParser(description="Start Safe-DS Runner on a specific port.")
    parser.add_argument('--port', type=int, default=5000, help='Port on which to run the python server.')
    args = parser.parse_args()
    setup_pipeline_execution()
    logging.info("Starting Safe-DS Runner on port %s", str(args.port))
    # Only bind to host=127.0.0.1. Connections from other devices should not be accepted
    WSGIServer(('127.0.0.1', args.port), app).serve_forever()
