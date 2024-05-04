import traceback
import warnings

from safeds_runner.server.messages._from_server import StacktraceEntry


def get_stacktrace_for_error(error: BaseException) -> list[StacktraceEntry]:
    """
    Create a simplified stacktrace for an error.

    Parameters
    ----------
    error:
        Caught error.

    Returns
    -------
    backtrace_info:
        List containing file and line information for each stack frame.
    """
    frames = traceback.extract_tb(error.__traceback__)
    return [
        StacktraceEntry(file=frame.filename, line=frame.lineno)
        for frame in reversed(list(frames))
    ]


def get_stacktrace_for_warning(warning: warnings.WarningMessage) -> list[StacktraceEntry]:
    """
    Create a simplified stacktrace for a warning.

    Parameters
    ----------
    warning:
        Caught warning.

    Returns
    -------
    backtrace_info:
        List containing file and line information for each stack frame.
    """
    return [StacktraceEntry(file=warning.filename, line=warning.lineno)]
