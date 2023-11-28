"""Module that contains functions for creating and validating messages exchanged with the vscode extension."""

import typing

message_type_program = "program"
message_type_placeholder_query = "placeholder_query"
message_type_placeholder_type = "placeholder_type"
message_type_placeholder_value = "placeholder_value"
message_type_runtime_error = "runtime_error"
message_type_runtime_progress = "runtime_progress"

message_types = [
    message_type_program,
    message_type_placeholder_query,
    message_type_placeholder_type,
    message_type_placeholder_value,
    message_type_runtime_error,
    message_type_runtime_progress,
]


def create_placeholder_description(name: str, placeholder_type: str) -> dict[str, typing.Any]:
    """Create the message data of a placeholder description message containing only name and type."""
    return {"name": name, "type": placeholder_type}


def create_placeholder_value(name: str, placeholder_type: str, value: typing.Any) -> dict[str, typing.Any]:
    """Create the message data of a placeholder value message containing name, type and the actual value."""
    return {"name": name, "type": placeholder_type, "value": value}


def create_runtime_error_description(message: str, backtrace: list[dict[str, typing.Any]]) -> dict[str, typing.Any]:
    """Create the message data of a runtime error message containing error information and a backtrace."""
    return {"message": message, "backtrace": backtrace}


def create_runtime_progress_done() -> str:
    """Create the message data of a runtime progress message containing 'done'."""
    return "done"


def validate_program_message(message_data: dict[str, typing.Any] | str) -> tuple[bool, str | None]:
    """Validate the message data of a program message."""
    if not isinstance(message_data, dict):
        return False, "Message data is not a JSON object"
    if "code" not in message_data:
        return False, "No 'code' parameter given"
    if "main" not in message_data:
        return False, "No 'main' parameter given"
    if (
        not isinstance(message_data["main"], dict)
        or "modulepath" not in message_data["main"]
        or "module" not in message_data["main"]
        or "pipeline" not in message_data["main"]
    ):
        return False, "Invalid 'main' parameter given"
    if len(message_data["main"]) != 3:
        return False, "Invalid 'main' parameter given"
    if not isinstance(message_data["code"], dict):
        return False, "Invalid 'code' parameter given"
    code: dict = message_data["code"]
    for key in code:
        if not isinstance(code[key], dict):
            return False, "Invalid 'code' parameter given"
        next_dict: dict = code[key]
        for next_key in next_dict:
            if not isinstance(next_dict[next_key], str):
                return False, "Invalid 'code' parameter given"
    return True, None


def validate_placeholder_query_message(message_data: dict[str, typing.Any] | str) -> tuple[bool, str | None]:
    """Validate the message data of a placeholder query message."""
    if not isinstance(message_data, str):
        return False, "Message data is not a string"
    return True, None
