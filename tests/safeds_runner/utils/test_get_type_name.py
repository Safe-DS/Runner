from __future__ import annotations

from typing import Any

import pytest
from safeds.data.tabular.containers import Table
from safeds_runner.utils._get_type_name import get_type_name


@pytest.mark.parametrize(
    argnames=("value", "type_"),
    argvalues=[
        (True, "bool"),
        (1.23, "float"),
        (1, "int"),
        ("abc", "str"),
        (object(), "object"),
        (None, "NoneType"),
        (lambda x: x + 1, "function"),
        (Table({"a": [1], "b": [2]}), "Table"),
    ],
    ids=[
        "bool",
        "float",
        "int",
        "str",
        "object",
        "none",
        "function",
        "table",
    ],
)
def test_should_return_python_type_name(value: Any, type_: str) -> None:
    assert get_type_name(value=value) == type_
