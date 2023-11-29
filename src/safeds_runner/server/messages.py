"""Module that contains functions for creating and validating messages exchanged with the vscode extension."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from typing import Any

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
    """
    A message object, which is exchanged between the runner and the VS Code extension.

    Parameters
    ----------
    type : str
        Type that identifies the kind of message.
    id : str
        ID that identifies the execution where this message belongs to.
    data : Any
        Message data section. Differs between message types.
    """

    type: str
    id: str
    data: Any

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Message:
        """
        Create a new Message object from a dictionary.

        Parameters
        ----------
        d : dict[str, Any]
            Dictionary which should contain all needed fields.

        Returns
        -------
        Message
            Dataclass which contains information copied from the provided dictionary.
        """
        return Message(**d)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert this dataclass to a dictionary.

        Returns
        -------
        dict[str, Any]
            Dictionary containing all the fields which are part of this dataclass.
        """
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class MessageDataProgram:
    """
    Message data for a program message.

    Parameters
    ----------
    code : dict[str, dict[str, str]]
        A dictionary containing the code needed for executed,
        in a virtual filesystem. Keys of the outer dictionary are the module path, keys of the inner dictionary are the
        module name. The values of the inner dictionary is the python code for each module.
    main : ProgramMainInformation
        Information where the main pipeline (the pipeline to be executed) is located.
    """

    code: dict[str, dict[str, str]]
    main: ProgramMainInformation

    @staticmethod
    def from_dict(d: dict[str, Any]) -> MessageDataProgram:
        """
        Create a new MessageDataProgram object from a dictionary.

        Parameters
        ----------
        d : dict[str, Any]
            Dictionary which should contain all needed fields.

        Returns
        -------
        MessageDataProgram
            Dataclass which contains information copied from the provided dictionary.
        """
        return MessageDataProgram(d["code"], ProgramMainInformation.from_dict(d["main"]))

    def to_dict(self) -> dict[str, Any]:
        """
        Convert this dataclass to a dictionary.

        Returns
        -------
        dict[str, Any]
            Dictionary containing all the fields which are part of this dataclass.
        """
        return dataclasses.asdict(self)  # pragma: no cover


@dataclass(frozen=True)
class ProgramMainInformation:
    """
    Information that can be used to locate a pipeline.

    Parameters
    ----------
    modulepath : str
        Path, where the main module is located.
    module : str
        Safe-DS module name.
    pipeline : str
        Safe-DS pipeline name.
    """

    modulepath: str
    module: str
    pipeline: str

    @staticmethod
    def from_dict(d: dict[str, Any]) -> ProgramMainInformation:
        """
        Create a new ProgramMainInformation object from a dictionary.

        Parameters
        ----------
        d : dict[str, Any]
            Dictionary which should contain all needed fields.

        Returns
        -------
        ProgramMainInformation
            Dataclass which contains information copied from the provided dictionary.
        """
        return ProgramMainInformation(**d)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert this dataclass to a dictionary.

        Returns
        -------
        dict[str, Any]
            Dictionary containing all the fields which are part of this dataclass.
        """
        return dataclasses.asdict(self)  # pragma: no cover


def create_placeholder_description(name: str, type_: str) -> dict[str, str]:
    """
    Create the message data of a placeholder description message containing only name and type.

    Parameters
    ----------
    name : str
        Name of the placeholder.
    type_ : str
        Type of the placeholder.

    Returns
    -------
    dict[str, str]
        Message data of "placeholder_type" messages.
    """
    return {"name": name, "type": type_}


def create_placeholder_value(name: str, type_: str, value: Any) -> dict[str, Any]:
    """
    Create the message data of a placeholder value message containing name, type and the actual value.

    Parameters
    ----------
    name : str
        Name of the placeholder.
    type_ : str
        Type of the placeholder.
    value : Any
        Value of the placeholder.

    Returns
    -------
    dict[str, str]
        Message data of "placeholder_value" messages.
    """
    return {"name": name, "type": type_, "value": value}


def create_runtime_error_description(message: str, backtrace: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Create the message data of a runtime error message containing error information and a backtrace.

    Parameters
    ----------
    message : str
        Error information message.
    backtrace : list[dict[str, Any]]
        Python backtrace of the error. Each list entry represents a stack frame.

    Returns
    -------
    dict[str, Any]
        Message data of "runtime_error" messages.
    """
    return {"message": message, "backtrace": backtrace}


def create_runtime_progress_done() -> str:
    """
    Create the message data of a runtime progress message containing 'done'.

    Returns
    -------
    str
        Message data of "runtime_progress" messages.
    """
    return "done"


def parse_validate_message(message: str) -> tuple[Message | None, str | None, str | None]:
    """
    Validate the basic structure of a received message string and return a parsed message object.

    Parameters
    ----------
    message : str
        Message string, that should be in JSON format.

    Returns
    -------
    tuple[Message | None, str | None, str | None]
        A tuple containing either a message or a detailed error description and a short error message.
    """
    try:
        message_dict: dict[str, Any] = json.loads(message)
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


def validate_program_message_data(message_data: dict[str, Any] | str) -> tuple[MessageDataProgram | None, str | None]:
    """
    Validate the message data of a program message.

    Parameters
    ----------
    message_data : dict[str, Any] | str
        Message data dictionary or string.

    Returns
    -------
    tuple[MessageDataProgram | None, str | None]
        A tuple containing either a validated message data object or an error message.
    """
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


def validate_placeholder_query_message_data(message_data: dict[str, Any] | str) -> tuple[str | None, str | None]:
    """
    Validate the message data of a placeholder query message.

    Parameters
    ----------
    message_data : dict[str, Any] | str
        Message data dictionary or string.

    Returns
    -------
    tuple[str | None, str | None]
        A tuple containing either a validated message data as a string or an error message.
    """
    if not isinstance(message_data, str):
        return None, "Message data is not a string"
    return message_data, None
