from __future__ import annotations

from abc import ABC
from typing import Any

from pydantic import BaseModel, ConfigDict


class MessageFromServer(BaseModel):
    """
    Message sent from the server to the client.

    Attributes
    ----------
    event:
        Event type of the message.
    payload:
        Payload of the message.
    """

    event: str
    payload: MessageFromServerPayload

    model_config = ConfigDict(extra="forbid")


class MessageFromServerPayload(BaseModel, ABC):
    """
    Base class for payloads of messages sent from the server to the client.

    Attributes
    ----------
    run_id:
        Identifier for the program run.
    """

    run_id: str


class PlaceholderValueMessagePayload(MessageFromServerPayload):
    """
    Payload for a 'placeholder_value' message.

    Attributes
    ----------
    run_id:
        Identifier for the program run.
    placeholder_name:
        Name of the placeholder.
    type:
        Python type of the placeholder at runtime.
    value:
        Value of the placeholder. Must be JSON-serializable.
    window:
        Window of the full value included as value in the message.
    """

    run_id: str
    placeholder_name: str
    type: str
    value: Any
    window: Window | None = None

    model_config = ConfigDict(extra="forbid")


class Window(BaseModel):
    """
    Window of a placeholder value. A window with start=0 and size=full_size is equivalent to the full value.

    Attributes
    ----------
    start:
        Start index of the window.
    size:
        Size of the window.
    full_size:
       Size of the full value.
    """

    start: int
    size: int
    full_size: int

    model_config = ConfigDict(extra="forbid")


class RuntimeWarningMessagePayload(MessageFromServerPayload):
    """
    Payload for a 'runtime_warning' message.

    Attributes
    ----------
    run_id:
        Identifier for the program run.
    message:
        Warning message.
    stacktrace:
        Stacktrace of the warning. Entries closest to the source of the warning come first.
    """

    run_id: str
    message: str
    stacktrace: list[StacktraceEntry]

    model_config = ConfigDict(extra="forbid")


class RuntimeErrorMessagePayload(MessageFromServerPayload):
    """
    Payload for a 'runtime_error' message.

    Attributes
    ----------
    run_id:
        Identifier for the program run.
    message:
        Error message.
    stacktrace:
        Stacktrace of the error. Entries closest to the source of the error come first.
    """

    run_id: str
    message: str
    stacktrace: list[StacktraceEntry]

    model_config = ConfigDict(extra="forbid")


class StacktraceEntry(BaseModel):
    """
    Entry in a stacktrace. Python provides no column information, so only the file and line are available.

    Attributes
    ----------
    file:
        File where the error occurred.
    line:
        Line number where the error occurred.
    """

    file: str
    line: int | None = None

    model_config = ConfigDict(extra="forbid")


class ProgressMessagePayload(MessageFromServerPayload):
    """
    Payload for a 'progress' message.

    Attributes
    ----------
    run_id:
        Identifier for the program run.
    placeholder_name:
        Name of the placeholder.
    percentage:
        Percentage of completion in the range [0, 100].
    message:
        Optional message to be displayed.
    """

    run_id: str
    placeholder_name: str
    percentage: int
    message: str | None = None

    model_config = ConfigDict(extra="forbid")


class DoneMessagePayload(MessageFromServerPayload):
    """
    Payload for a 'done' message.

    Attributes
    ----------
    run_id:
        Identifier for the program run.
    """

    run_id: str

    model_config = ConfigDict(extra="forbid")


def create_placeholder_value_message(
    run_id: str,
    placeholder_name: str,
    type_: str,
    value: Any,
    window: Window | None = None,
) -> MessageFromServer:
    """Create a 'placeholder_value' message."""
    return MessageFromServer(
        event="placeholder_value",
        payload=PlaceholderValueMessagePayload(
            run_id=run_id,
            placeholder_name=placeholder_name,
            type=type_,
            value=value,
            window=window,
        ),
    )


def create_runtime_warning_message(
    run_id: str,
    message: str,
    stacktrace: list[StacktraceEntry],
) -> MessageFromServer:
    """Create a 'runtime_warning' message."""
    return MessageFromServer(
        event="runtime_warning",
        payload=RuntimeWarningMessagePayload(run_id=run_id, message=message, stacktrace=stacktrace),
    )


def create_runtime_error_message(run_id: str, message: str, stacktrace: list[StacktraceEntry]) -> MessageFromServer:
    """Create a 'runtime_error' message."""
    return MessageFromServer(
        event="runtime_error",
        payload=RuntimeErrorMessagePayload(run_id=run_id, message=message, stacktrace=stacktrace),
    )


def create_progress_message(
    run_id: str,
    placeholder_name: str,
    percentage: int,
    message: str | None = None,
) -> MessageFromServer:
    """Create a 'progress' message."""
    return MessageFromServer(
        event="progress",
        payload=ProgressMessagePayload(
            run_id=run_id,
            placeholder_name=placeholder_name,
            percentage=percentage,
            message=message,
        ),
    )


def create_done_message(run_id: str) -> MessageFromServer:
    """Create a 'done' message."""
    return MessageFromServer(event="done", payload=DoneMessagePayload(run_id=run_id))
