"""Module containing the server, endpoints and utility functions."""
import asyncio
import json
import logging
import signal
from asyncio import Lock
from typing import Any

import socketio
import uvicorn
from pydantic import ValidationError

from ._pipeline_manager import PipelineManager
from ._process_manager import ProcessManager
from .messages._from_server import DoneMessagePayload, MessageFromServer
from .messages._to_server import RunMessagePayload


class SafeDsServer:
    def __init__(self) -> None:
        self._sio = socketio.AsyncServer(logger=True, async_mode="asgi")
        self._app = socketio.ASGIApp(self._sio)
        self._process_manager = ProcessManager()
        self._pipeline_manager = PipelineManager(self._process_manager)
        self._lock = Lock()

        # Add event handlers
        signal.signal(signal.SIGINT, self._interrupt_handler)
        self._process_manager.on_message(self._send_message)
        self._register_event_handlers(self._sio)

    async def startup(self, port: int) -> None:
        """Start the server on the specified port."""
        self._process_manager.startup()

        logging.info("Starting Safe-DS Runner on port %s...", str(port))
        config = uvicorn.config.Config(self._app, host="127.0.0.1", port=port)
        server = uvicorn.server.Server(config)
        await server.serve()

    async def shutdown(self) -> None:
        """Shutdown the server."""
        self._process_manager.shutdown()
        await self._sio.shutdown()

    def _interrupt_handler(self, _signal: Any, _frame: Any) -> None:
        """Handle the interrupt signal."""
        asyncio.get_running_loop().create_task(self.shutdown())

    async def _send_message(self, message: MessageFromServer) -> None:
        """
        Send a message to all interested clients.

        Parameters
        ----------
        message:
            Message to be sent.
        """
        await self._lock.acquire()

        # Send the message to the client
        await self._sio.emit(
            message.event,
            message.payload.model_dump_json(),
            to=message.payload.run_id,
        )

        # Close the room if the message is a done message
        if isinstance(message.payload, DoneMessagePayload):
            await self._sio.close_room(message.payload.run_id)

        self._lock.release()

    def _register_event_handlers(self, sio: socketio.AsyncServer) -> None:
        @sio.event
        async def run(sid: str, payload: Any = None) -> None:
            try:
                if isinstance(payload, str):
                    payload = json.loads(payload)
                run_message_payload = RunMessagePayload(**payload)
            except (TypeError, ValidationError):
                logging.exception("Invalid run message payload: %s", payload)
                return

            await sio.enter_room(sid, run_message_payload.run_id)
            await self._pipeline_manager.execute_pipeline(run_message_payload)

        @sio.event
        def shutdown(_sid: str, *_args: Any) -> None:
            logging.info("Shutting down...")
            signal.raise_signal(signal.SIGINT)

        @sio.on("*")
        def catch_all(event: str, *_args: Any) -> None:
            logging.exception("Invalid message type: %s", event)
