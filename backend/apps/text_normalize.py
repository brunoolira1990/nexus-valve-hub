from __future__ import annotations

from collections.abc import Mapping


def to_operational_upper(value):
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().upper()


def normalize_operational_fields(payload: dict, field_names: set[str]) -> dict:
    for key in field_names:
        if key in payload:
            payload[key] = to_operational_upper(payload.get(key))
    return payload


def normalize_operational_mapping(
    payload: Mapping,
    *,
    include_fields: set[str] | None = None,
    exclude_fields: set[str] | None = None,
) -> dict:
    out = dict(payload)
    ex = exclude_fields or set()
    for key, value in out.items():
        if include_fields is not None and key not in include_fields:
            continue
        if key in ex:
            continue
        if isinstance(value, str):
            out[key] = to_operational_upper(value)
    return out
