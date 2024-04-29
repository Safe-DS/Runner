from __future__ import annotations

import asyncio
import logging
import multiprocessing
import os
from asyncio import CancelledError, Task
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, ParamSpec, TypeAlias, TypeVar

if TYPE_CHECKING:
    import queue
    from collections.abc import Coroutine
    from concurrent.futures import Future
    from multiprocessing.managers import DictProxy, SyncManager

    from safeds_runner.server.messages._from_server import MessageFromServer


class ProcessManager:
    """Service for managing processes and communicating between them."""

    def __init__(self) -> None:
        self._state: _State = "initial"
        self._on_message_callbacks: set[Callable[[MessageFromServer], Coroutine[Any, Any, None]]] = set()

    @cached_property
    def _manager(self) -> SyncManager:
        if multiprocessing.get_start_method() != "spawn":
            multiprocessing.set_start_method("spawn", force=True)
        return multiprocessing.Manager()

    @cached_property
    def _message_queue(self) -> queue.Queue[MessageFromServer]:
        return self._manager.Queue()

    @cached_property
    def _message_queue_consumer(self) -> Task:
        async def _consume() -> None:
            """Consume messages from the message queue and call all registered callbacks."""
            executor = ThreadPoolExecutor(max_workers=1)
            loop = asyncio.get_running_loop()

            try:
                while self._state != "shutdown":
                    message = await loop.run_in_executor(executor, self._message_queue.get)
                    for callback in self._on_message_callbacks:
                        asyncio.run_coroutine_threadsafe(callback(message), loop)
            except CancelledError as error:  # pragma: no cover
                logging.info("Message queue terminated: %s", error.__repr__())  # pragma: no cover
            finally:
                executor.shutdown(wait=True, cancel_futures=True)

        return asyncio.create_task(_consume())

    @cached_property
    def _worker_process_pool(self) -> ProcessPoolExecutor:
        return ProcessPoolExecutor(
            max_workers=4,
            mp_context=multiprocessing.get_context("spawn"),
        )

    def startup(self) -> None:
        """
        Start the process manager and all associated processes.

        Before calling this method, the process manager is not fully initialized and cannot be used.
        """
        if self._state == "started":
            return

        if self._state == "initial":
            # Initialize all cached properties
            _manager = self._manager
            _message_queue = self._message_queue
            _message_queue_consumer = self._message_queue_consumer
            _worker_process_pool = self._worker_process_pool

            # Set state to started before warm up to prevent endless recursion
            self._state = "started"

            # Warm up one worker process
            self.submit(_warmup_worker)
        elif self._state == "shutdown":
            raise RuntimeError("ProcessManager has already been shutdown.")

    def shutdown(self) -> None:
        """
        Shutdown the process manager and all associated processes.

        This method should be called before the program exits. After calling this method, the process manager can no
        longer be used.
        """
        if self._state == "started":
            self._worker_process_pool.shutdown(wait=True, cancel_futures=True)
            self._message_queue_consumer.cancel()
            self._manager.shutdown()
        self._state = "shutdown"

    def create_shared_dict(self) -> DictProxy:
        """Create a dictionary that can be accessed by multiple processes."""
        return self._manager.dict()

    def on_message(self, callback: Callable[[MessageFromServer], Coroutine[Any, Any, None]]) -> Unregister:
        """
        Get notified when a message is received from another process.

        Parameters
        ----------
        callback:
            The function to call when a message is received.

        Returns
        -------
        unregister:
            A function that can be called to stop receiving messages.
        """
        self._on_message_callbacks.add(callback)
        return lambda: self._on_message_callbacks.remove(callback)

    def get_queue(self) -> queue.Queue[MessageFromServer]:
        """Get the message queue that is used to communicate between processes."""
        return self._message_queue

    _P = ParamSpec("_P")
    _T = TypeVar("_T")

    def submit(self, func: Callable[_P, _T], /, *args: _P.args, **kwargs: _P.kwargs) -> Future[_T]:
        """Submit a function to be executed by a worker process."""
        return self._worker_process_pool.submit(func, *args, **kwargs)


def _warmup_worker() -> None:
    """Import packages that worker processes will definitely need."""
    # Skip warmup if being tested. This greatly speeds up test execution.
    if "PYTEST_CURRENT_TEST" in os.environ:
        return

    from safeds.data.tabular.containers import Table  # pragma: no cover

    Table({"a": [1]}).get_column("a").plot_histogram()  # pragma: no cover


_State: TypeAlias = Literal["initial", "started", "shutdown"]
Unregister = Callable[[], None]
