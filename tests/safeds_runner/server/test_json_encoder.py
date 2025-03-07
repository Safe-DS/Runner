from __future__ import annotations

import base64
import json
import math
from typing import Any

import pytest
from safeds.data.image.containers import Image
from safeds.data.labeled.containers import TabularDataset
from safeds.data.tabular.containers import Table
from safeds_runner.server._json_encoder import SafeDsEncoder


@pytest.mark.parametrize(
    argnames="data,expected_string",
    argvalues=[
        (
            TabularDataset(
                {"a": [1, 2], "b": [3.2, 4.0], "c": [math.nan, 5.6], "d": [5, -6]},
                "d",
            ),
            '{"a": [1, 2], "b": [3.2, 4.0], "c": [null, 5.6], "d": [5, -6]}',
        ),
        (
            Table({"a": [1, 2], "b": [3.2, 4.0], "c": [math.nan, 5.6], "d": [5, -6]}),
            '{"a": [1, 2], "b": [3.2, 4.0], "c": [null, 5.6], "d": [5, -6]}',
        ),
        (
            Image.from_bytes(
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC",
                ),
            ),
            (
                '{"format": "png", "bytes": '
                '"iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAADElEQVR4nGNgoBwAAABEAAHX40j9\\nAAAAAElFTkSuQmCC\\n"}'
            ),
        ),
    ],
    ids=["encode_tabular_dataset", "encode_table", "encode_image_png"],
)
def test_encoding_custom_types(data: Any, expected_string: str) -> None:
    assert json.dumps(data, cls=SafeDsEncoder) == expected_string


@pytest.mark.parametrize(argnames="data", argvalues=[(object())], ids=["encode_object"])
def test_encoding_unsupported_types(data: Any) -> None:
    with pytest.raises(TypeError):
        json.dumps(data, cls=SafeDsEncoder)
