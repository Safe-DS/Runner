import subprocess
from pathlib import Path
from typing import IO
import typing

_project_root: Path = Path(__file__).parent / ".." / ".." / ".."


def test_should_runner_start_successfully() -> None:
    process = subprocess.Popen(["poetry", "run", "safe-ds-runner"], cwd=_project_root, stderr=subprocess.PIPE)
    while process.poll() is None:
        process_line = str(typing.cast(IO[bytes], process.stderr).readline(), "utf-8").strip()
        # Wait for first line of log
        if process_line.startswith("INFO:root:Starting Safe-DS Runner"):
            process.kill()
            return
    assert process.poll() == 0
