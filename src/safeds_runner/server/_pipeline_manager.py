"""Module that contains the infrastructure for pipeline execution in child processes."""

from __future__ import annotations

import linecache
import logging
import os
import runpy
import traceback
import typing
import warnings
from functools import cached_property

from safeds_runner.memoization._memoization_map import MemoizationMap

from ._module_manager import InMemoryFinder
from .messages._from_server import (
    StacktraceEntry,
    create_done_message,
    create_runtime_error_message,
    create_runtime_warning_message,
)

if typing.TYPE_CHECKING:
    import queue

    from ._process_manager import ProcessManager
    from .messages._from_server import MessageFromServer
    from .messages._to_server import RunMessagePayload


class PipelineManager:
    """
    A PipelineManager handles the execution of pipelines and processing of results.

    This includes launching subprocesses and the communication between the
    subprocess and the main process using a shared message queue.
    """

    def __init__(self, process_manager: ProcessManager) -> None:
        self._process_manager = process_manager

    @cached_property
    def _memoization_map(self) -> MemoizationMap:
        return MemoizationMap(
            self._process_manager.create_shared_dict(),  # type: ignore[arg-type]
            self._process_manager.create_shared_dict(),  # type: ignore[arg-type]
        )

    async def execute_pipeline(self, payload: RunMessagePayload) -> None:
        """
        Run a Safe-DS pipeline.

        Parameters
        ----------
        payload:
            Information about the pipeline to run.
        """
        process = PipelineProcess(
            payload,
            self._process_manager.get_queue(),
            self._memoization_map,
        )
        await process.execute(self._process_manager)


class PipelineProcess:
    """A process that executes a Safe-DS pipeline."""

    def __init__(
        self,
        payload: RunMessagePayload,
        messages_queue: queue.Queue[MessageFromServer],
        memoization_map: MemoizationMap,
    ):
        """
        Create a new process which will execute the given pipeline, when started.

        Parameters
        ----------
        payload:
            Information about the pipeline to run.
        messages_queue:
            A queue to write outgoing messages to.
        memoization_map:
            A map to save results of memoizable functions in.
        """
        self._payload = payload
        self._messages_queue = messages_queue
        self._memoization_map = memoization_map

    def get_memoization_map(self) -> MemoizationMap:
        """
        Get the shared memoization map.

        Returns
        -------
        memoization_map:
            Memoization Map
        """
        return self._memoization_map

    def send_message(self, message: MessageFromServer) -> None:
        """
        Send a message to all interested clients.

        Parameters
        ----------
        message:
            Message to send.
        """
        self._messages_queue.put(message)

    async def execute(self, process_manager: ProcessManager) -> None:
        """
        Execute this pipeline in a process from the provided process pool.

        Results, progress and errors are communicated back to the main process.
        """
        future = process_manager.submit(self._execute)
        exception = future.exception()
        if exception is not None:
            self._catch_subprocess_error(exception)  # pragma: no cover

    def _execute(self) -> None:
        logging.info("Executing %s...", self._payload.main_absolute_module_name)

        pipeline_finder = InMemoryFinder(self._payload.code)
        pipeline_finder.attach()

        # Populate _current_pipeline global, so interface methods can access it
        global _current_pipeline_process  # noqa: PLW0603
        _current_pipeline_process = self

        if self._payload.cwd is not None:
            os.chdir(self._payload.cwd)  # pragma: no cover

        try:
            with warnings.catch_warnings(record=True) as collected_warnings:
                runpy.run_module(
                    self._payload.main_absolute_module_name,
                    run_name="__main__",
                    alter_sys=True,
                )
                self._send_warnings(collected_warnings)
        except BaseException as error:  # noqa: BLE001
            self._send_exception(error)
        finally:
            self.send_message(create_done_message(self._payload.run_id))
            # Needed for `getSource` to work correctly when the process is reused
            linecache.clearcache()
            pipeline_finder.detach()

    def _catch_subprocess_error(self, error: BaseException) -> None:
        # This is a callback to log an unexpected failure, executing this is never expected
        logging.exception("Pipeline process unexpectedly failed", exc_info=error)  # pragma: no cover

    def _send_warnings(self, warnings_: list[warnings.WarningMessage]) -> None:
        for warning in warnings_:
            self.send_message(
                create_runtime_warning_message(
                    run_id=self._payload.run_id,
                    message=str(warning.message),
                    stacktrace=[StacktraceEntry(file=warning.filename, line=warning.lineno)],
                ),
            )

    def _send_exception(self, exception: BaseException) -> None:
        self.send_message(
            create_runtime_error_message(
                run_id=self._payload.run_id,
                message=exception.__str__(),
                stacktrace=get_stacktrace(exception),
            ),
        )


# Pipeline process object visible in child process
_current_pipeline_process: PipelineProcess | None = None


def get_current_pipeline_process() -> PipelineProcess | None:
    """
    Get the current pipeline process.

    Returns
    -------
    current_pipeline:
        Current pipeline process.
    """
    return _current_pipeline_process


def get_stacktrace(error: BaseException) -> list[StacktraceEntry]:
    """
    Create a simplified stacktrace from an exception.

    Parameters
    ----------
    error:
        Caught exception.

    Returns
    -------
    backtrace_info:
        List containing file and line information for each stack frame.
    """
    frames = traceback.extract_tb(error.__traceback__)
    return [StacktraceEntry(file=frame.filename, line=int(frame.lineno)) for frame in reversed(list(frames))]
