from __future__ import annotations

from typing import Any

import pytest
from safeds.data.labeled.containers import TabularDataset

from safeds_runner.server._pipeline_manager import _get_placeholder_type


@pytest.mark.parametrize(
    argnames=("value", "type_"),
    argvalues=[
        (True, "Boolean"),
        (False, "Boolean"),
        (1.23, "Float"),
        (4.156e5, "Float"),
        (-1.23e5, "Float"),
        (1, "Int"),
        (-2, "Int"),
        (0, "Int"),
        ("abc", "String"),
        ("18", "String"),
        ("96.51615", "String"),
        ("True", "String"),
        ("False", "String"),
        ("1.3e5", "String"),
        (object(), "object"),
        (None, "Null"),
        (lambda x: x + 1, "Callable"),
        (TabularDataset({"a": [1], "b": [2]}, "a"), "Table"),
    ],
    ids=[
        "boolean_true",
        "boolean_false",
        "float",
        "float_exp",
        "float_negative",
        "int",
        "int_negative",
        "int_zero",
        "string",
        "string_int",
        "string_float",
        "string_boolean_true",
        "string_boolean_false",
        "string_float_exp",
        "object",
        "null",
        "callable",
        "tabular_dataset",
    ],
)
def test_should_placeholder_type_match_safeds_dsl_placeholder(value: Any, type_: str) -> None:
    assert _get_placeholder_type(value=value) == type_
