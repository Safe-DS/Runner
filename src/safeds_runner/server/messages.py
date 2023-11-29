"""Module that contains functions for creating and validating messages exchanged with the vscode extension."""
from __future__ import annotations

import typing
from typing import Any
import json
import dataclasses
from dataclasses import dataclass

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


@dataclass(frozen=True)
class Message:
    type: str
    id: str
    data: dict[str, Any]

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Message:
        return Message(**d)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class MessageDataProgram:
    code: dict[str, dict[str, str]]
    main: MessageDataProgramMain

    @staticmethod
    def from_dict(d: dict[str, Any]) -> MessageDataProgram:
        return MessageDataProgram(d["code"], MessageDataProgramMain.from_dict(d["main"]))

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class MessageDataProgramMain:
    modulepath: str
    module: str
    pipeline: str

    @staticmethod
    def from_dict(d: dict[str, Any]) -> MessageDataProgramMain:
        return MessageDataProgramMain(**d)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


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


def parse_validate_message(message: str) -> tuple[Message | None, str | None, str | None]:
    """Validate the basic structure of a received message and return a parsed message object."""
    try:
        message_dict: dict[str, typing.Any] = json.loads(message)
    except json.JSONDecodeError:
        return None, f"Invalid message received: {message}", "Invalid Message: not JSON"
    if "type" not in message_dict:
        return None, f"No message type specified in: {message}", "Invalid Message: no type"
    if "id" not in message_dict:
        return None, f"No message id specified in: {message}", "Invalid Message: no id"
    if "data" not in message_dict:
        return None, f"No message data specified in: {message}", "Invalid Message: no data"
    if not isinstance(message_dict["type"], str):
        return None, f"Message type is not a string: {message}", "Invalid Message: invalid type"
    if not isinstance(message_dict["id"], str):
        return None, f"Message id is not a string: {message}", "Invalid Message: invalid id"
    return Message.from_dict(message_dict), None, None


def validate_program_message_data(message_data: dict[str, typing.Any] | str) -> tuple[
    MessageDataProgram | None, str | None]:
    """Validate the message data of a program message."""
    if not isinstance(message_data, dict):
        return None, "Message data is not a JSON object"
    if "code" not in message_data:
        return None, "No 'code' parameter given"
    if "main" not in message_data:
        return None, "No 'main' parameter given"
    if (
        not isinstance(message_data["main"], dict)
        or "modulepath" not in message_data["main"]
        or "module" not in message_data["main"]
        or "pipeline" not in message_data["main"]
    ):
        return None, "Invalid 'main' parameter given"
    if len(message_data["main"]) != 3:
        return None, "Invalid 'main' parameter given"
    if not isinstance(message_data["code"], dict):
        return None, "Invalid 'code' parameter given"
    code: dict = message_data["code"]
    for key in code:
        if not isinstance(code[key], dict):
            return None, "Invalid 'code' parameter given"
        next_dict: dict = code[key]
        for next_key in next_dict:
            if not isinstance(next_dict[next_key], str):
                return None, "Invalid 'code' parameter given"
    return MessageDataProgram.from_dict(message_data), None


def validate_placeholder_query_message_data(message_data: dict[str, typing.Any] | str) -> tuple[str | None, str | None]:
    """Validate the message data of a placeholder query message."""
    if not isinstance(message_data, str):
        return None, "Message data is not a string"
    return message_data, None
