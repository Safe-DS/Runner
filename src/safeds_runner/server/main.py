"""Module containing the main entry point, for starting the Safe-DS runner."""

import argparse
import json
import logging
from importlib.metadata import version

import flask.app
import flask_sock
import simple_websocket
from flask import Flask
from flask_cors import CORS
from flask_sock import Sock

from safeds_runner.server import messages
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


app = create_flask_app()
sock = create_flask_websocket(app)
app_pipeline_manager = PipelineManager()


@sock.route("/WSMain")
def _ws_main(ws: simple_websocket.Server) -> None:
    ws_main(ws, app_pipeline_manager)  # pragma: no cover


def ws_main(ws: simple_websocket.Server, pipeline_manager: PipelineManager) -> None:
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
    pipeline_manager.set_new_websocket_target(ws)
    while True:
        # This would be a JSON message
        received_message: str = ws.receive()
        if received_message is None:
            logging.debug("Received EOF, closing connection")
            ws.close()
            return
        logging.debug("Received Message: %s", received_message)
        received_object, error_detail, error_short = parse_validate_message(received_message)
        if received_object is None:
            logging.error(error_detail)
            ws.close(message=error_short)
            return
        match received_object.type:
            case "program":
                program_data, invalid_message = messages.validate_program_message_data(received_object.data)
                if program_data is None:
                    logging.error("Invalid message data specified in: %s (%s)", received_message, invalid_message)
                    ws.close(None, invalid_message)
                    return
                # This should only be called from the extension as it is a security risk
                pipeline_manager.execute_pipeline(program_data, received_object.id)
            case "placeholder_query":
                placeholder_query_data, invalid_message = messages.validate_placeholder_query_message_data(
                    received_object.data,
                )
                if placeholder_query_data is None:
                    logging.error("Invalid message data specified in: %s (%s)", received_message, invalid_message)
                    ws.close(None, invalid_message)
                    return
                placeholder_type, placeholder_value = pipeline_manager.get_placeholder(
                    received_object.id,
                    placeholder_query_data,
                )
                # send back a value message
                if placeholder_type is not None:
                    send_websocket_message(
                        ws,
                        Message(
                            message_type_placeholder_value,
                            received_object.id,
                            create_placeholder_value(placeholder_query_data, placeholder_type, placeholder_value),
                        ),
                    )
                else:
                    # Send back empty type / value, to communicate that no placeholder exists (yet)
                    # Use name from query to allow linking a response to a request on the peer
                    send_websocket_message(
                        ws,
                        Message(
                            message_type_placeholder_value,
                            received_object.id,
                            create_placeholder_value(placeholder_query_data, "", ""),
                        ),
                    )
            case _:
                if received_object.type not in messages.message_types:
                    logging.warning("Invalid message type: %s", received_object.type)


def send_websocket_message(connection: simple_websocket.Server, message: Message) -> None:
    """
    Send any message to the VS Code extension.

    Parameters
    ----------
    connection : simple_websocket.Server
        Websocket connection.
    message : Message
        Object that will be sent.
    """
    connection.send(json.dumps(message.to_dict()))


def main() -> None:  # pragma: no cover
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
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version="%(prog)s {version}".format(version=version("safe-ds-runner")),
    )
    args = parser.parse_args()
    logging.info("Starting Safe-DS Runner on port %s", str(args.port))
    # Only bind to host=127.0.0.1. Connections from other devices should not be accepted
    WSGIServer(("127.0.0.1", args.port), app).serve_forever()


if __name__ == "__main__":
    main()  # pragma: no cover
