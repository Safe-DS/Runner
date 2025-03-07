import pytest

from safeds_runner.server._process_manager import ProcessManager


def test_should_not_startup_after_shutdown() -> None:
    manager = ProcessManager()
    manager.shutdown()
    with pytest.raises(RuntimeError, match="ProcessManager has already been shutdown."):
        manager.startup()
