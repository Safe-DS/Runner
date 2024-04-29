from __future__ import annotations

from abc import ABC

from pydantic import BaseModel, ConfigDict


class IncomingMessage(BaseModel):
    event: str
    payload: IncomingMessagePayload

    model_config = ConfigDict(extra="forbid")


class IncomingMessagePayload(BaseModel, ABC):
    pass


class RunMessagePayload(IncomingMessagePayload):
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


class ShutdownMessagePayload(IncomingMessagePayload):
    model_config = ConfigDict(extra="forbid")


def create_shutdown_message() -> IncomingMessage:
    return IncomingMessage(event="shutdown", payload=ShutdownMessagePayload())
