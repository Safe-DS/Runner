"""Module containing JSON encoding utilities for Safe-DS types."""
import json
import base64
import math
from typing import Any

from safeds.data.image.containers import Image
from safeds.data.image.typing import ImageFormat
from safeds.data.tabular.containers import Table


class SafeDSEncoder(json.JSONEncoder):
    """JSON Encoder for custom Safe-DS types."""

    def default(self, o: Any) -> Any:
        """
        Check if values are custom Safe-DS types (such as Table or Image) convert them to a serializable representation.
        If a value is not handled here, the default encoding implementation is called.

        Parameters
        ----------
        o: Any
            An object that needs to be encoded to JSON.

        Returns
        -------
        Any
            The passed object represented in a way that is serializable to JSON.
        """
        if isinstance(o, Table):
            dict_with_nan_infinity = o.to_dict()
            # Convert NaN / Infinity to None, as the JSON encoder generates invalid JSON otherwise
            return {key: [value if not isinstance(value, float) or math.isfinite(value) else None for value in
                          dict_with_nan_infinity[key]] for key in dict_with_nan_infinity}
        if isinstance(o, Image):
            # Send images together with their format
            match o.format:
                case ImageFormat.JPEG:
                    return {"format": o.format.value, "bytes": str(base64.encodebytes(o._repr_jpeg_()), "utf-8")}
                case ImageFormat.PNG:
                    return {"format": o.format.value, "bytes": str(base64.encodebytes(o._repr_png_()), "utf-8")}
            return ""
        return json.JSONEncoder.default(self, o)
