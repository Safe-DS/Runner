from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError
from safeds_runner.server._messages import ProgramMessageData, QueryMessageData

if TYPE_CHECKING:
    from regex import Regex


@pytest.mark.parametrize(
    argnames=["data", "exception_regex"],
    argvalues=[
        (
            {"main": {"modulepath": "1", "module": "2", "pipeline": "3"}},
            re.compile(r"code[\s\S]*missing"),
        ),
        (
            {"code": {"": {"entry": ""}}},
            re.compile(r"main[\s\S]*missing"),
        ),
        (
            {"code": {"": {"entry": ""}}, "main": {"modulepath": "1", "module": "2"}},
            re.compile(r"main.pipeline[\s\S]*missing"),
        ),
        (
            {"code": {"": {"entry": ""}}, "main": {"modulepath": "1", "pipeline": "3"}},
            re.compile(r"main.module[\s\S]*missing"),
        ),
        (
            {"code": {"": {"entry": ""}}, "main": {"module": "2", "pipeline": "3"}},
            re.compile(r"main.modulepath[\s\S]*missing"),
        ),
        (
            {
                "code": {"": {"entry": ""}},
                "main": {"modulepath": "1", "module": "2", "pipeline": "3", "other": "4"},
            },
            re.compile(r"main.other[\s\S]*extra_forbidden"),
        ),
        (
            {"code": "a", "main": {"modulepath": "1", "module": "2", "pipeline": "3"}},
            re.compile(r"code[\s\S]*dict_type"),
        ),
        (
            {"code": {"a": "n"}, "main": {"modulepath": "1", "module": "2", "pipeline": "3"}},
            re.compile(r"code\.a[\s\S]*dict_type"),
        ),
        (
            {
                "code": {"a": {"b": {"c": "d"}}},
                "main": {"modulepath": "1", "module": "2", "pipeline": "3"},
            },
            re.compile(r"code\.a\.b[\s\S]*string_type"),
        ),
        (
            {
                "code": {},
                "main": {"modulepath": "1", "module": "2", "pipeline": "3"},
                "cwd": 1,
            },
            re.compile(r"cwd[\s\S]*string_type"),
        ),
    ],
    ids=[
        "program_no_code",
        "program_no_main",
        "program_invalid_main1",
        "program_invalid_main2",
        "program_invalid_main3",
        "program_invalid_main4",
        "program_invalid_code1",
        "program_invalid_code2",
        "program_invalid_code3",
        "program_invalid_cwd",
    ],
)
def test_should_fail_message_validation_reason_program(data: dict[str, Any], exception_regex: str) -> None:
    with pytest.raises(ValidationError, match=exception_regex):
        ProgramMessageData(**data)


@pytest.mark.parametrize(
    argnames=["data", "exception_regex"],
    argvalues=[
        (
            {"a": "v"},
            re.compile(r"name[\s\S]*missing"),
        ),
        (
            {"name": "v", "window": {"begin": "a"}},
            re.compile(r"window.begin[\s\S]*int_parsing"),
        ),
        (
            {"name": "v", "window": {"size": "a"}},
            re.compile(r"window.size[\s\S]*int_parsing"),
        ),
    ],
    ids=[
        "missing_name",
        "wrong_type_begin",
        "wrong_type_size",
    ],
)
def test_should_fail_message_validation_reason_placeholder_query(
    data: dict[str, Any],
    exception_regex: Regex,
) -> None:
    with pytest.raises(ValidationError, match=exception_regex):
        QueryMessageData(**data)
