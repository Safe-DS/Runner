from __future__ import annotations

from abc import ABC

from pydantic import BaseModel, ConfigDict


class OutgoingMessage(BaseModel):
    event: str
    payload: OutgoingMessagePayload

    model_config = ConfigDict(extra="forbid")


class OutgoingMessagePayload(BaseModel, ABC):
    run_id: str


class PlaceholderValueMessagePayload(OutgoingMessagePayload):
    run_id: str
    placeholder_name: str
    type: str
    value: str
    window: Window | None = None

    model_config = ConfigDict(extra="forbid")


class Window(BaseModel):
    start: int
    size: int
    max: int

    model_config = ConfigDict(extra="forbid")


class RuntimeWarningMessagePayload(OutgoingMessagePayload):
    run_id: str
    message: str
    stacktrace: list[StacktraceEntry]

    model_config = ConfigDict(extra="forbid")


class RuntimeErrorMessagePayload(OutgoingMessagePayload):
    run_id: str
    message: str
    stacktrace: list[StacktraceEntry]

    model_config = ConfigDict(extra="forbid")


class StacktraceEntry(BaseModel):
    file: str
    line: int

    model_config = ConfigDict(extra="forbid")


class ProgressMessagePayload(OutgoingMessagePayload):
    run_id: str
    placeholder_name: str
    percentage: int
    message: str | None = None

    model_config = ConfigDict(extra="forbid")


class DoneMessagePayload(OutgoingMessagePayload):
    run_id: str

    model_config = ConfigDict(extra="forbid")


def create_placeholder_value_message(
    run_id: str,
    placeholder_name: str,
    type_: str,
    value: str,
    window: Window | None = None,
) -> OutgoingMessage:
    return OutgoingMessage(
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
) -> OutgoingMessage:
    return OutgoingMessage(
        event="runtime_warning",
        payload=RuntimeWarningMessagePayload(run_id=run_id, message=message, stacktrace=stacktrace),
    )


def create_runtime_error_message(run_id: str, message: str, stacktrace: list[StacktraceEntry]) -> OutgoingMessage:
    return OutgoingMessage(
        event="runtime_error",
        payload=RuntimeErrorMessagePayload(run_id=run_id, message=message, stacktrace=stacktrace),
    )


def create_progress_message(
    run_id: str,
    placeholder_name: str,
    percentage: int,
    message: str | None = None,
) -> OutgoingMessage:
    return OutgoingMessage(
        event="progress",
        payload=ProgressMessagePayload(
            run_id=run_id,
            placeholder_name=placeholder_name,
            percentage=percentage,
            message=message,
        ),
    )


def create_done_message(run_id: str) -> OutgoingMessage:
    return OutgoingMessage(event="done", payload=DoneMessagePayload(run_id=run_id))
