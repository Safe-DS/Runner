from __future__ import annotations

from abc import ABC

from pydantic import BaseModel, ConfigDict


class MessageToServer(BaseModel):
    event: str
    payload: MessageToServerPayload

    model_config = ConfigDict(extra="forbid")


class MessageToServerPayload(BaseModel, ABC):
    pass


class RunMessagePayload(MessageToServerPayload):
    run_id: str
    code: list[VirtualModule]
    main_absolute_module_name: str
    cwd: str | None = None
    table_window: Window | None = None

    model_config = ConfigDict(extra="forbid")


class VirtualModule(BaseModel):
    """
    Information about a virtual module.

    Parameters
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
    return MessageToServer(event="shutdown", payload=ShutdownMessagePayload())
