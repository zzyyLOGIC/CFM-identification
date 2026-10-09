"""Strict JSON used at untrusted text and persisted-artifact boundaries."""
from __future__ import annotations
import json
from typing import Any


def loads(text: str) -> Any:
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError("DUPLICATE_JSON_KEY: " + key)
            obj[key] = value
        return obj

    def nonfinite(value):
        raise ValueError("NONFINITE_JSON: " + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)


def canonical(value: Any) -> str:
    """Type-sensitive comparison: JSON false must not compare equal to integer 0."""
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False)
