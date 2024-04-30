from __future__ import annotations

from abc import ABC

from pydantic import BaseModel, ConfigDict


class MessageToServer(BaseModel):
    """
    Message sent from the client to the server.

    Attributes
    ----------
    event:
        Event type of the message.
    payload:
        Payload of the message.
    """

    event: str
    payload: MessageToServerPayload

    model_config = ConfigDict(extra="forbid")


class MessageToServerPayload(BaseModel, ABC):
    """Base class for payloads of messages sent from the client to the server."""


class RunMessagePayload(MessageToServerPayload):
    """
    Payload for a 'run' message.

    Attributes
    ----------
    run_id:
        Identifier for the program run.
    code:
        Code of the program.
    main_absolute_module_name:
        Absolute name of the main module.
    cwd:
        Current working directory.
    table_window:
        Window to get for placeholders of type 'Table'.
    """

    run_id: str
    code: list[VirtualModule]
    main_absolute_module_name: str
    cwd: str | None = None
    table_window: Window | None = None

    model_config = ConfigDict(extra="forbid")


class VirtualModule(BaseModel):
    """
    Information about a virtual module.

    Attributes
    ----------
    absolute_module_name:
        Path of the module (`from <absolute_module_name> import ...`).
    code:
        Code of the module.
    """

    absolute_module_name: str
    code: str

    model_config = ConfigDict(extra="forbid")


class Window(BaseModel):
    """
    Window of a placeholder value.

    Attributes
    ----------
    start:
        Start index of the window.
    size:
        Size of the window.
    """

    start: int
    size: int

    model_config = ConfigDict(extra="forbid")


class ShutdownMessagePayload(MessageToServerPayload):
    model_config = ConfigDict(extra="forbid")


def create_run_message(
    run_id: str,
    code: list[VirtualModule],
    main_absolute_module_name: str,
    cwd: str | None = None,
    table_window: Window | None = None,
) -> MessageToServer:
    """Create a 'run' message."""
    return MessageToServer(
        event="run",
        payload=RunMessagePayload(
            run_id=run_id,
            code=code,
            main_absolute_module_name=main_absolute_module_name,
            cwd=cwd,
            table_window=table_window,
        ),
    )


def create_shutdown_message() -> MessageToServer:
    """Create a 'shutdown' message."""
    return MessageToServer(event="shutdown", payload=ShutdownMessagePayload())
