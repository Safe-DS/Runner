import warnings

from safeds_runner.utils._get_stacktrace import get_stacktrace_for_error, get_stacktrace_for_warning


class TestGetStacktraceForError:
    def test_get_stacktrace_for_error(self):
        try:
            raise RuntimeError("An error occurred")  # noqa: TRY301
        except RuntimeError as error:
            stacktrace = get_stacktrace_for_error(error)
            assert len(stacktrace) == 1
            assert stacktrace[0].file.endswith("test_get_stacktrace.py")
            assert stacktrace[0].line == 7


class TestGetStacktraceForWarning:
    def test_get_stacktrace_for_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.warn("A warning occurred", RuntimeWarning, stacklevel=1)
            stacktrace = get_stacktrace_for_warning(w[0])
            assert len(stacktrace) == 1
            assert stacktrace[0].file.endswith("test_get_stacktrace.py")
            assert stacktrace[0].line == 20
