from __future__ import annotations

import asyncio
import json
import logging
import multiprocessing
import os
import threading
from concurrent.futures import ProcessPoolExecutor
from functools import cached_property
from threading import Lock
from typing import TYPE_CHECKING, Literal, ParamSpec, TypeAlias, TypeVar

if TYPE_CHECKING:
    from asyncio import Future
    from collections.abc import Callable
    from multiprocessing.managers import DictProxy, SyncManager
    from queue import Queue

    from safeds_runner.server._messages import Message


class ProcessManager:
    """Service for managing processes and communicating between them."""

    def __init__(self, targets: list[asyncio.Queue]):
        self._websocket_target = targets

        self._lock = Lock()
        self._state: _State = "initial"

    @cached_property
    def _manager(self) -> SyncManager:
        return multiprocessing.Manager()

    @cached_property
    def _message_queue(self) -> Queue[Message]:
        return self._manager.Queue()

    @cached_property
    def _process_pool(self) -> ProcessPoolExecutor:
        return ProcessPoolExecutor(
            max_workers=4,
            mp_context=multiprocessing.get_context("spawn"),
        )

    @cached_property
    def _messages_queue_thread(self) -> threading.Thread:
        return threading.Thread(target=self._handle_queue_messages, daemon=True, args=(asyncio.get_event_loop(),))

    def _handle_queue_messages(self, event_loop: asyncio.AbstractEventLoop) -> None:
        """
        Relay messages from pipeline processes to the currently connected websocket endpoint.

        Should be used in a dedicated thread.

        Parameters
        ----------
        event_loop:
            Event Loop that handles websocket connections.
        """
        try:
            while True:
                message = self.get_next_message()
                message_encoded = json.dumps(message.to_dict())
                # only send messages to the same connection once
                for connection in set(self._websocket_target):
                    asyncio.run_coroutine_threadsafe(connection.put(message_encoded), event_loop)
        except BaseException as error:  # noqa: BLE001  # pragma: no cover
            logging.warning("Message queue terminated: %s", error.__repr__())  # pragma: no cover

    def startup(self):
        """
        Start the process manager and all associated processes.

        Before calling this method, the process manager is not fully initialized and cannot be used.
        """
        if self._state == "started":
            return

        self._lock.acquire()
        if self._state == "initial":
            _manager = self._manager
            _message_queue = self._message_queue
            _process_pool = self._process_pool
            self._messages_queue_thread.start()

            self._state = "started"
            self.submit(_warmup_worker)  # Warm up one worker process
        elif self._state == "shutdown":
            self._lock.release()
            raise RuntimeError("ProcessManager has already been shutdown.")
        self._lock.release()

    def shutdown(self):
        """
        Shutdown the process manager and all associated processes.

        This method should be called before the program exits. After calling this method, the process manager can no
        longer be used.
        """
        self._lock.acquire()
        if self._state == "started":
            self._manager.shutdown()
            self._process_pool.shutdown(wait=True, cancel_futures=True)
        self._state = "shutdown"
        self._lock.release()

    def create_shared_dict(self) -> DictProxy:
        """Create a dictionary that can be accessed by multiple processes."""
        self.startup()
        return self._manager.dict()

    def get_next_message(self) -> Message:
        """Get the next message from the message queue."""
        self.startup()
        return self._message_queue.get()

    def get_queue(self) -> Queue[Message]:
        """Get the message queue that is used to communicate between processes."""
        self.startup()
        return self._message_queue

    _P = ParamSpec("_P")
    _T = TypeVar("_T")

    def submit(self, func: Callable[_P, _T], /, *args: _P, **kwargs: _P) -> Future[_T]:
        """Submit a function to be executed by a worker process."""
        self.startup()
        return self._process_pool.submit(func, *args, **kwargs)


def _warmup_worker():
    """Import packages that worker processes will definitely need."""
    # Skip warmup if being tested. This greatly speeds up test execution.
    if "PYTEST_CURRENT_TEST" in os.environ:
        return

    from safeds.data.tabular.containers import Table

    Table({"a": [1]}).get_column("a").plot_histogram()


_State: TypeAlias = Literal["initial", "started", "shutdown"]