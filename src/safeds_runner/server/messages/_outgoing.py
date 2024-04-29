from __future__ import annotations

from abc import ABC

from pydantic import BaseModel, ConfigDict


class OutgoingMessage(BaseModel):
    event: str
    payload: OutgoingMessagePayload

    model_config = ConfigDict(extra="forbid")


class OutgoingMessagePayload(BaseModel, ABC):
    id: str | None


class PlaceholderValueMessagePayload(OutgoingMessagePayload):
    id: str
    placeholder_name: str
    type: str
    value: str
    window: Window | None

    model_config = ConfigDict(extra="forbid")


class Window(BaseModel):
    start: int
    size: int
    max: int

    model_config = ConfigDict(extra="forbid")


class RuntimeWarningMessagePayload(OutgoingMessagePayload):
    id: str
    message: str
    stacktrace: list[StacktraceEntry]

    model_config = ConfigDict(extra="forbid")


class RuntimeErrorMessagePayload(OutgoingMessagePayload):
    id: str
    message: str
    stacktrace: list[StacktraceEntry]

    model_config = ConfigDict(extra="forbid")


class StacktraceEntry(BaseModel):
    file: str
    line: int

    model_config = ConfigDict(extra="forbid")


class ProgressMessagePayload(OutgoingMessagePayload):
    id: str
    placeholder_name: str
    percentage: int
    message: str | None = None

    model_config = ConfigDict(extra="forbid")


class DoneMessagePayload(OutgoingMessagePayload):
    id: str
    data: None = None

    model_config = ConfigDict(extra="forbid")


def create_placeholder_value_message(
    id_: str,
    placeholder_name: str,
    type_: str,
    value: str,
    window: Window | None,
) -> OutgoingMessage:
    return OutgoingMessage(
        event="placeholder_value",
        payload=PlaceholderValueMessagePayload(
            id=id_,
            placeholder_name=placeholder_name,
            type=type_,
            value=value,
            window=window,
        ),
    )


def create_runtime_warning_message(id_: str, message: str, stacktrace: list[StacktraceEntry]) -> OutgoingMessage:
    return OutgoingMessage(
        event="runtime_warning",
        payload=RuntimeWarningMessagePayload(id=id_, message=message, stacktrace=stacktrace),
    )


def create_runtime_error_message(id_: str, message: str, stacktrace: list[StacktraceEntry]) -> OutgoingMessage:
    return OutgoingMessage(
        event="runtime_error",
        payload=RuntimeErrorMessagePayload(id=id_, message=message, stacktrace=stacktrace),
    )


def create_progress_message(
    id_: str,
    placeholder_name: str,
    percentage: int,
    message: str | None = None,
) -> OutgoingMessage:
    return OutgoingMessage(
        event="progress",
        payload=ProgressMessagePayload(
            id=id_,
            placeholder_name=placeholder_name,
            percentage=percentage,
            message=message,
        ),
    )


def create_done_message(id_: str) -> OutgoingMessage:
    return OutgoingMessage(event="done", payload=DoneMessagePayload(id=id_))
