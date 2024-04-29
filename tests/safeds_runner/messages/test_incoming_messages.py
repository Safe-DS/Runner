from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from safeds_runner.server.messages._to_server import RunMessagePayload

if TYPE_CHECKING:
    from typing import Any


@pytest.mark.parametrize(
    argnames=["data", "exception_regex"],
    argvalues=[
        (  # valid_minimal
            {
                "run_id": "id",
                "code": [],
                "main_absolute_module_name": "main",
            },
            None,
        ),
        (  # valid_with_code
            {
                "run_id": "id",
                "code": [
                    {"absolute_module_name": "main", "code": "code"},
                ],
                "main_absolute_module_name": "main",
            },
            None
        ),
        (  # valid_with_cwd
            {
                "run_id": "id",
                "code": [],
                "main_absolute_module_name": "main",
                "cwd": "cwd",
            },
            None,
        ),
        (  # valid_with_table_window
            {
                "run_id": "id",
                "code": [],
                "main_absolute_module_name": "main",
                "table_window": {"start": 0, "size": 1},
            },
            None,
        ),
        (  # invalid_no_run_id
            {
                "code": [],
                "main_absolute_module_name": "main",
            },
            re.compile(r"run_id[\s\S]*missing"),
        ),
        (  # invalid_wrong_type_run_id
            {
                "run_id": 1,
                "code": [],
                "main_absolute_module_name": "main",
            },
            re.compile(r"run_id[\s\S]*string_type"),
        ),
        (  # invalid_no_code
            {
                "run_id": "id",
                "main_absolute_module_name": "main",
            },
            re.compile(r"code[\s\S]*missing"),
        ),
        (  # invalid_wrong_type_code
            {
                "run_id": "id",
                "code": "a",
                "main_absolute_module_name": "main",
            },
            re.compile(r"code[\s\S]*list_type"),
        ),
        (  # invalid_no_main_absolute_module_name
            {
                "run_id": "id",
                "code": [],
            },
            re.compile(r"main_absolute_module_name[\s\S]*missing"),
        ),
        (  # invalid_wrong_type_main_absolute_module_name
            {
                "run_id": "id",
                "code": [],
                "main_absolute_module_name": 1,
            },
            re.compile(r"main_absolute_module_name[\s\S]*string_type"),
        ),
        (  # invalid_wrong_type_cwd
            {
                "run_id": "id",
                "code": [],
                "main_absolute_module_name": "main",
                "cwd": 1,
            },
            re.compile(r"cwd[\s\S]*string_type"),
        ),
        (  # invalid_wrong_type_table_window
            {
                "run_id": "id",
                "code": [],
                "main_absolute_module_name": "main",
                "table_window": 1,
            },
            re.compile(r"table_window[\s\S]*model_type"),
        )
    ],
    ids=[
        "valid_minimal",
        "valid_with_code",
        "valid_with_cwd",
        "valid_with_table_window",
        "invalid_no_run_id",
        "invalid_wrong_type_run_id",
        "invalid_no_code",
        "invalid_wrong_type_code",
        "invalid_no_main_absolute_module_name",
        "invalid_wrong_type_main_absolute_module_name",
        "invalid_wrong_type_cwd",
        "invalid_wrong_type_table_window",
    ],
)
def test_validate_run_message_payload(data: dict[str, Any], exception_regex: str | None) -> None:
    if exception_regex is None:
        RunMessagePayload(**data)
    else:
        with pytest.raises(ValidationError, match=exception_regex):
            RunMessagePayload(**data)
