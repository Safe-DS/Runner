import base64
import math
from io import BytesIO
from typing import Any

import pytest
from safeds.data.image.containers import Image
from safeds.data.image.typing import ImageFormat
from safeds.data.tabular.containers import Table
import json

from safeds_runner.server.json_encoder import SafeDsEncoder


@pytest.mark.parametrize(argnames="data,expected_string", argvalues=[(
        Table.from_dict({'a': [1, 2], 'b': [3.2, 4.0], 'c': [math.nan, 5.6], 'd': [5, -6]}),
        '{"a": [1, 2], "b": [3.2, 4.0], "c": [null, 5.6], "d": [5, -6]}'),
    (Image(BytesIO(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5"
                                    "+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC")), ImageFormat.PNG),
     '{"format": "png", "bytes": '
     '"iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAADElEQVR4nGNgoBwAAABEAAHX40j9\\nAAAAAElFTkSuQmCC\\n"}'),
    (Image(BytesIO(base64.b64decode(
        "/9j/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wgALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAAA//aAAgBAQAAAAE//9k=")),
           ImageFormat.JPEG),
     '{"format": "jpeg", "bytes": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a'
     '\\nHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAHwAAAQUBAQEB\\nAQEAAAAAAAAAAAECAwQFBgcICQoL'
     '/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1Fh'
     '\\nByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZ'
     '\\nWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXG\\nx8jJytLT1NXW19jZ2uHi4'
     '+Tl5ufo6erx8vP09fb3+Pn6/9oACAEBAAA/AEr/2Q==\\n"}')],
                         ids=["encode_table", "encode_image_png", "encode_image_jpeg"])
def test_encoding_custom_types(data: Any, expected_string: str) -> None:
    assert json.dumps(data, cls=SafeDsEncoder) == expected_string


@pytest.mark.parametrize(argnames="data", argvalues=[(object())],
                         ids=["encode_object"])
def test_encoding_unsupported_types(data: Any) -> None:
    with pytest.raises(TypeError):
        json.dumps(data, cls=SafeDsEncoder)
