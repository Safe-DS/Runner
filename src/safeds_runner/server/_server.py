"""Module containing the server, endpoints and utility functions."""
import asyncio
import logging
import sys
from typing import Any

import socketio
import uvicorn
from pydantic import ValidationError

from safeds_runner.server.messages._messages import (
    ProgramMessage,
)

from ._pipeline_manager import PipelineManager
from ._process_manager import ProcessManager
from .messages._outgoing import OutgoingMessage


class SafeDsServer:
    def __init__(self) -> None:
        self._sio = socketio.AsyncServer(logger=True, async_mode="asgi")
        self._app = socketio.ASGIApp(self._sio)
        self._process_manager = ProcessManager()
        self._pipeline_manager = PipelineManager(self._process_manager)

        # Add event handlers
        self._process_manager.on_message(self.send_message)
        self._register_event_handlers(self._sio)

    async def startup(self, port: int) -> None:
        """Start the server on the specified port."""
        await self._process_manager.startup()

        logging.info("Starting Safe-DS Runner on port %s", str(port))
        config = uvicorn.config.Config(self._app, host="127.0.0.1", port=port)
        server = uvicorn.server.Server(config)
        await server.serve()

    async def shutdown(self) -> None:
        """Shutdown the server."""
        await self._process_manager.shutdown()
        await self._sio.shutdown()

    async def send_message(self, message: OutgoingMessage) -> None:
        """
        Send a message to all interested clients.

        Parameters
        ----------
        message:
            Message to be sent.
        """
        asyncio.run_coroutine_threadsafe(
            self._sio.emit(
                message.event,
                message.payload.model_dump_json(),
                to=message.payload.run_id,
            ),
            asyncio.get_event_loop(),
        )

    def _register_event_handlers(self, sio: socketio.AsyncServer) -> None:
        @sio.event
        async def run(sid: str, payload: Any) -> None:
            try:
                program_message = ProgramMessage(**payload)
            except (TypeError, ValidationError):
                logging.exception("Invalid message data specified in: %s", payload)
                return

            await sio.enter_room(sid, program_message.id)
            await self._pipeline_manager.execute_pipeline(
                program_message.data,
                program_message.id,
            )
            # await sio.leave_room(sid, program_message.id)

        # @sio.event
        # async def placeholder_query(_sid: str, payload: Any) -> None:
        #     try:
        #         placeholder_query_message = QueryMessage(**payload)
        #     except (TypeError, ValidationError):
        #         logging.exception("Invalid message data specified in: %s", payload)
        #         return
        #
        #     placeholder_type, placeholder_value = self._pipeline_manager.get_placeholder(
        #         placeholder_query_message.id,
        #         placeholder_query_message.data.name,
        #     )
        #
        #     if placeholder_type is None:
        #         # Send back empty type / value, to communicate that no placeholder exists (yet)
        #         # Use name from query to allow linking a response to a request on the peer
        #         data = json.dumps(create_placeholder_value(placeholder_query_message.data, "", ""))
        #         await sio.emit(message_type_placeholder_value, data, to=placeholder_query_message.id)
        #         return
        #
        #     try:
        #         data = json.dumps(
        #             create_placeholder_value(
        #                 placeholder_query_message.data,
        #                 placeholder_type,
        #                 placeholder_value,
        #             ),
        #             cls=SafeDsEncoder,
        #         )
        #     except TypeError:
        #         # if the value can't be encoded send back that the value exists but is not displayable
        #         data = json.dumps(
        #             create_placeholder_value(
        #                 placeholder_query_message.data,
        #                 placeholder_type,
        #                 "<Not displayable>",
        #             ),
        #         )
        #
        #     await sio.emit(message_type_placeholder_value, data, to=placeholder_query_message.id)

        @sio.event
        async def shutdown(_sid: str, _payload: Any):
            logging.debug("Requested shutdown...")
            await self.shutdown()
            sys.exit(0)

        @sio.on("*")
        async def catch_all(event: str):
            logging.warning("Invalid message type: %s", event)
