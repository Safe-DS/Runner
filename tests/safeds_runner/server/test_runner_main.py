from __future__ import annotations

import subprocess
import typing
from pathlib import Path
from typing import IO

from safeds_runner.utils._tree_kill import tree_kill

_project_root: Path = Path(__file__).parent / ".." / ".." / ".."


def test_should_runner_start_successfully() -> None:
    subprocess._USE_VFORK = False  # Do not fork the subprocess as it is unsafe to do
    process = subprocess.Popen(["poetry", "run", "safe-ds-runner", "start"], cwd=_project_root, stderr=subprocess.PIPE)
    while process.poll() is None:
        process_line = str(typing.cast(IO[bytes], process.stderr).readline(), "utf-8").strip()
        # Wait for first line of log
        if "Starting Safe-DS Runner" in process_line:
            tree_kill(process.pid)
            return
    assert process.poll() == 0
