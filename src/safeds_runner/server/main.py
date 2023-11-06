import argparse

import json
import logging
from typing import Any, Optional

from flask import Flask, request
from flask_cors import CORS
from flask_sock import Sock

from safeds_runner.server.module_manager import execute_pipeline

app = Flask(__name__)
# Websocket Configuration
app.config['SOCK_SERVER_OPTIONS'] = {'ping_interval': 25}
sock = Sock(app)
# Allow access from VSCode extension
CORS(app, resources={r"/*": {"origins": "vscode-webview://*"}})


## HTTP Route
@app.route("/PostRunProgram", methods=["POST"])
def post_run_program():
    """
    Args should contain every source file that was generated
    code: ["<package>" => ["<file>" => "<code>", ...], ...]
    main: {"package": <package; Value of Package directive on Safe-DS module>, "module": <module; Name of Safe-DS source file>, "pipeline": <pipeline; Name of executable Pipeline>}
    :return: Tuple: (Result String, HTTP Code)
    """
    logging.debug(f"{request.path}: {request.form}")
    if not request.is_json:
        return "Body is not JSON", 400
    request_data = request.get_json()
    # Validate
    valid, invalid_message = validate_message(request_data)
    if not valid:
        return invalid_message, 400
    code = request_data["code"]
    main = request_data["main"]
    # Execute
    # Dynamically define Safe-DS Modules only in our runtime scope
    # TODO forward memoization map here
    context_globals = {}
    # This should only be called from the extension as it is a security risk
    result = execute_pipeline(code, main['package'], main['module'], main['pipeline'], context_globals)
    return json.dumps(result), 200


@sock.route("/WSRunProgram")
def ws_run_program(ws):
    logging.debug(f"Request to WSRunProgram")
    send_message(ws, "test", "test")
    while True:
        # This would be a JSON message
        received_message: str = ws.receive()
        logging.debug(f"> Received Message: {received_message}")
        try:
            received_object: dict[str, Any] = json.loads(received_message)
        except json.JSONDecodeError:
            logging.warn(f"Invalid message received: {received_message}")
            ws.close(None)
            return
        if "type" not in received_object:
            logging.warn(f"No message type specified in: {received_message}")
            ws.close(None)
            return
        match received_object["type"]:
            case "program":
                if "data" not in received_object:
                    logging.warn(f"No message data specified in: {received_message}")
                    ws.close(None)
                    return
                request_data = received_object["data"]
                valid, invalid_message = validate_message(request_data)
                if not valid:
                    logging.warn(f"Invalid message data specified in: {received_message} ({invalid_message})")
                    ws.close(None)
                    return
                code = request_data["code"]
                main = request_data["main"]
                # Execute
                # Dynamically define Safe-DS Modules only in our runtime scope
                # TODO forward memoization map here
                context_globals = {"connection": ws, "send_value": send_value}
                # This should only be called from the extension as it is a security risk
                execute_pipeline(code, main['package'], main['module'], main['pipeline'], context_globals)


def send_value(connection, name: str, var_type: str, value: str):
    send_message(connection, "value", {"name": name, "type": var_type, "value": value})


def send_message(connection, msg_type: str, msg_data):
    message = {"type": msg_type, "data": msg_data}
    connection.send(json.dumps(message))


def validate_message(message: dict[str, Any]) -> (bool, Optional[str]):
    if "code" not in message:
        return False, "No 'code' parameter given"
    if "main" not in message:
        return False, "No 'main' parameter given"
    if "package" not in message["main"] or "module" not in message["main"] or "pipeline" not in message["main"]:
        return False, "Invalid 'main' parameter given"
    if len(message["main"]) != 3:
        return False, "Invalid 'main' parameter given"
    main: dict[str, str] = message["main"]
    if not isinstance(message["code"], dict):
        return False, "Invalid 'code' parameter given"
    code: dict = message["code"]
    for key in code.keys():
        if not isinstance(key, str):
            return False, "Invalid 'code' parameter given"
        if not isinstance(code[key], dict):
            return False, "Invalid 'code' parameter given"
        next_dict: dict = code[key]
        for next_key in next_dict.keys():
            if not isinstance(next_key, str):
                return False, "Invalid 'code' parameter given"
            if not isinstance(next_dict[next_key], str):
                return False, "Invalid 'code' parameter given"
    return True, None


if __name__ == "__main__":
    # Allow prints to be unbuffered by default
    import functools
    import builtins
    builtins.print = functools.partial(print, flush=True)

    logging.getLogger().setLevel(logging.DEBUG)
    from gevent import monkey

    monkey.patch_all()
    from gevent.pywsgi import WSGIServer

    parser = argparse.ArgumentParser(description="Start Safe-DS Runner on a specific port.")
    parser.add_argument('--port', type=int, default=5000, help='Port on which to run the python server.')
    args = parser.parse_args()
    logging.info(f"Starting Safe-DS Runner on port {args.port}")
    # TODO Maybe only bind to host=127.0.0.1? Connections from other devices would then not be accepted
    WSGIServer(('0.0.0.0', args.port), app).serve_forever()
