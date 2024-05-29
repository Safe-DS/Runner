"""Module that contains functions for creating and validating messages exchanged with the vscode extension."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

message_type_program = "program"
message_type_placeholder_query = "placeholder_query"
message_type_placeholder_type = "placeholder_type"
message_type_placeholder_value = "placeholder_value"
message_type_runtime_error = "runtime_error"
message_type_runtime_progress = "runtime_progress"
message_type_shutdown = "shutdown"

message_types = [
    message_type_program,
    message_type_placeholder_query,
    message_type_placeholder_type,
    message_type_placeholder_value,
    message_type_runtime_error,
    message_type_runtime_progress,
    message_type_shutdown,
]


@dataclass(frozen=True)
class Message:
    """
    A message object, which is exchanged between the runner and the VS Code extension.

    Parameters
    ----------
    type:
        Type that identifies the kind of message.
    id:
        ID that identifies the execution where this message belongs to.
    data:
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
        d:
            Dictionary which should contain all needed fields.

        Returns
        -------
        message:
            Dataclass which contains information copied from the provided dictionary.
        """
        return Message(**d)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert this dataclass to a dictionary.

        Returns
        -------
        dict:
            Dictionary containing all the fields which are part of this dataclass.
        """
        return dataclasses.asdict(self)


class ProgramMessage(BaseModel):
    """
    A message object for a `program` message.

    Parameters
    ----------
    data:
        Data of the program message.
    """

    id: str
    data: ProgramMessageData

    model_config = ConfigDict(extra="forbid")


class ProgramMessageData(BaseModel):
    """
    Message data for a `program` message.

    Parameters
    ----------
    code:
        A dictionary containing the code needed for executed,
        in a virtual filesystem. Keys of the outer dictionary are the module path, keys of the inner dictionary are the
        module name. The values of the inner dictionary is the python code for each module.
    main:
        Information where the main pipeline (the pipeline to be executed) is located.
    cwd:
        Current working directory to use for execution. If not set, the default working directory is used.
    """

    code: dict[str, dict[str, str]]
    main: ProgramMessageMainInformation
    cwd: str | None = None

    model_config = ConfigDict(extra="forbid")


class ProgramMessageMainInformation(BaseModel):
    """
    Information that can be used to locate a pipeline.

    Parameters
    ----------
    modulepath:
        Path, where the main module is located.
    module:
        Safe-DS module name.
    pipeline:
        Safe-DS pipeline name.
    """

    modulepath: str
    module: str
    pipeline: str

    model_config = ConfigDict(extra="forbid")


class QueryMessage(BaseModel):
    """
    A message object for a `placeholder_query` message.

    Parameters
    ----------
    data:
        Data of the placeholder query message.
    """

    id: str
    data: QueryMessageData

    model_config = ConfigDict(extra="forbid")


class QueryMessageWindow(BaseModel):
    """
    Information that is used to create a subset of the data of a placeholder.

    Parameters
    ----------
    begin:
        Index of the first entry that should be sent. May be present if a windowed query is required.
    size:
        Max. amount of entries that should be sent. May be present if a windowed query is required.
    """

    begin: int | None = None
    size: int | None = None

    model_config = ConfigDict(extra="forbid")


class QueryMessageData(BaseModel):
    """
    Information used to query a placeholder with optional window bounds. Only complex types like tables are affected by window bounds.

    Parameters
    ----------
    name:
        Placeholder name that is queried.
    window:
        Window bounds for requesting only a subset of the available data.
    """

    name: str
    window: QueryMessageWindow = Field(default_factory=QueryMessageWindow)

    model_config = ConfigDict(extra="forbid")


def create_placeholder_description(name: str, type_: str) -> dict[str, str]:
    """
    Create the message data of a placeholder description message containing only name and type.

    Parameters
    ----------
    name:
        Name of the placeholder.
    type_:
        Type of the placeholder.

    Returns
    -------
    message_data:
        Message data of "placeholder_type" messages.
    """
    return {"name": name, "type": type_}


def create_placeholder_value(placeholder_query: QueryMessageData, type_: str, value: Any) -> dict[str, Any]:
    """
    Create the message data of a placeholder value message containing name, type and the actual value.

    If the query only requests a subset of the data and the placeholder type supports this,
    the response will contain only a subset and the information about the subset.

    Parameters
    ----------
    placeholder_query:
        Query of the placeholder.
    type_:
        Type of the placeholder.
    value:
        Value of the placeholder.

    Returns
    -------
    message_data:
        Message data of "placeholder_value" messages.
    """
    import safeds.data.labeled.containers
    import safeds.data.tabular.containers

    message: dict[str, Any] = {"name": placeholder_query.name, "type": type_}
    # Start Index >= 0
    start_index = max(
        placeholder_query.window.begin if placeholder_query.window.begin is not None else 0,
        0,
    )
    # Length >= 0
    length = max(placeholder_query.window.size, 0) if placeholder_query.window.size is not None else None
    if isinstance(value, safeds.data.labeled.containers.TabularDataset):
        value = value.to_table()

    if isinstance(value, safeds.data.tabular.containers.Table) and (
        placeholder_query.window.begin is not None or placeholder_query.window.size is not None
    ):
        max_index = value.row_count
        value = value.slice_rows(start=start_index, length=length)
        window_information: dict[str, int] = {
            "begin": start_index,
            "size": value.row_count,
            "max": max_index,
        }
        message["window"] = window_information
    message["value"] = value
    return message


def create_runtime_error_description(message: str, backtrace: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Create the message data of a runtime error message containing error information and a backtrace.

    Parameters
    ----------
    message:
        Error information message.
    backtrace:
        Python backtrace of the error. Each list entry represents a stack frame.

    Returns
    -------
    message_data:
        Message data of "runtime_error" messages.
    """
    return {"message": message, "backtrace": backtrace}


def create_runtime_progress_done() -> str:
    """
    Create the message data of a runtime progress message containing 'done'.

    Returns
    -------
    str:
        Message data of "runtime_progress" messages.
    """
    return "done"


def parse_validate_message(
    message: str,
) -> tuple[Message | None, str | None, str | None]:
    """
    Validate the basic structure of a received message string and return a parsed message object.

    Parameters
    ----------
    message:
        Message string, that should be in JSON format.

    Returns
    -------
    message_or_error:
        A tuple containing either a message or a detailed error description and a short error message.
    """
    try:
        message_dict: dict[str, Any] = json.loads(message)
    except json.JSONDecodeError:
        return None, f"Invalid message received: {message}", "Invalid Message: not JSON"
    if "type" not in message_dict:
        return (
            None,
            f"No message type specified in: {message}",
            "Invalid Message: no type",
        )
    elif "id" not in message_dict:
        return None, f"No message id specified in: {message}", "Invalid Message: no id"
    elif "data" not in message_dict:
        return (
            None,
            f"No message data specified in: {message}",
            "Invalid Message: no data",
        )
    elif not isinstance(message_dict["type"], str):
        return (
            None,
            f"Message type is not a string: {message}",
            "Invalid Message: invalid type",
        )
    elif not isinstance(message_dict["id"], str):
        return (
            None,
            f"Message id is not a string: {message}",
            "Invalid Message: invalid id",
        )
    else:
        return Message(**message_dict), None, None
