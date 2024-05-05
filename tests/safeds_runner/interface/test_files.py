import tempfile
from datetime import UTC, datetime
from pathlib import Path

from safeds_runner import absolute_path, file_mtime


def test_file_mtime_existing() -> None:
    with tempfile.NamedTemporaryFile() as file:
        mtime = file_mtime(file.name)
        assert mtime is not None


def test_file_mtime_existing_list() -> None:
    with tempfile.NamedTemporaryFile() as file:
        mtime = file_mtime([file.name, file.name])
        assert isinstance(mtime, list)
        assert all(it is not None for it in mtime)


def test_file_mtime_missing() -> None:
    mtime = file_mtime(f"file_not_exists.{datetime.now(tz=UTC).timestamp()}")
    assert mtime is None


def test_absolute_path() -> None:
    result = absolute_path("table.csv")
    assert Path(result).is_absolute()


def test_absolute_path_list() -> None:
    result = absolute_path(["table.csv"])
    assert all(Path(it).is_absolute() for it in result)
