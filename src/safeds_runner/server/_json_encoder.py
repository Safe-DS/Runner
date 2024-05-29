"""Module containing JSON encoding utilities for Safe-DS types."""

from __future__ import annotations

import base64
import json
import math
from typing import Any


class SafeDsEncoder(json.JSONEncoder):
    """JSON Encoder for custom Safe-DS types."""

    def default(self, o: Any) -> Any:
        """
        Convert specific Safe-DS types to a JSON-serializable representation.

        If values are custom Safe-DS types (such as Table or Image) they are converted to a serializable representation.
        If a value is not handled here, the default encoding implementation is called.
        In case of Tables, note that NaN values are converted to JSON null values.

        Parameters
        ----------
        o:
            An object that needs to be encoded to JSON.

        Returns
        -------
        json_serializable:
            The passed object represented in a way that is serializable to JSON.
        """
        # Moving these imports to the top drastically increases startup time
        from safeds.data.image.containers import Image
        from safeds.data.labeled.containers import TabularDataset
        from safeds.data.tabular.containers import Table

        if isinstance(o, TabularDataset):
            o = o.to_table()

        if isinstance(o, Table):
            dict_with_nan_infinity = o.to_dict()
            # Convert NaN / Infinity to None, as the JSON encoder generates invalid JSON otherwise
            return {
                key: [
                    value if not isinstance(value, float) or math.isfinite(value) else None
                    for value in dict_with_nan_infinity[key]
                ]
                for key in dict_with_nan_infinity
            }
        elif isinstance(o, Image):
            # Send images together with their format, by default images are encoded only as PNG
            return {
                "format": "png",
                "bytes": str(base64.encodebytes(o._repr_png_()), "utf-8"),
            }
        else:
            return json.JSONEncoder.default(self, o)
