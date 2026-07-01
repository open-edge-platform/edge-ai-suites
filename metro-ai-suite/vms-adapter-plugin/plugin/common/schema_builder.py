# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Dynamically build a Pydantic model from a JSON Schema dict at runtime.

Used by Analytics App shims to convert a JSON Schema fetched from a Analytics App's
OpenAPI spec into a live Pydantic model that the plugin uses for:
  * Returning params_schema to the UI via GET /v1/analytics-apps/discover
  * Validating payloads at POST /v1/analytics-apps/{app_id}/start
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, create_model

# JSON Schema type → Python type mapping
_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "object": dict,
    "array": list,
}


def _resolve_python_type(prop: dict[str, Any]) -> type:
    """Map a JSON Schema property definition to a Python type."""
    # anyOf: [{"type": X}, {"type": "null"}]  →  Optional[X]
    any_of = prop.get("anyOf")
    if any_of:
        non_null = [p for p in any_of if p.get("type") != "null"]
        if non_null:
            inner = _TYPE_MAP.get(non_null[0].get("type", "string"), str)
            return Optional[inner]  # type: ignore[return-value]
        return Optional[str]  # type: ignore[return-value]

    json_type = prop.get("type", "string")
    return _TYPE_MAP.get(json_type, str)


def _build_field(prop: dict[str, Any], required: bool) -> tuple[type, Any]:
    """Return (python_type, FieldInfo) for a single JSON Schema property."""
    python_type = _resolve_python_type(prop)

    field_kwargs: dict[str, Any] = {}

    # description / title
    if "description" in prop:
        field_kwargs["description"] = prop["description"]
    if "title" in prop:
        field_kwargs["title"] = prop["title"]

    # numeric constraints
    if "minimum" in prop:
        field_kwargs["ge"] = prop["minimum"]
    if "maximum" in prop:
        field_kwargs["le"] = prop["maximum"]
    if "exclusiveMinimum" in prop:
        field_kwargs["gt"] = prop["exclusiveMinimum"]
    if "exclusiveMaximum" in prop:
        field_kwargs["lt"] = prop["exclusiveMaximum"]

    # string constraints
    if "minLength" in prop:
        field_kwargs["min_length"] = prop["minLength"]
    if "maxLength" in prop:
        field_kwargs["max_length"] = prop["maxLength"]
    if "pattern" in prop:
        field_kwargs["pattern"] = prop["pattern"]

    # default / required
    if "default" in prop:
        default = prop["default"]
        field_kwargs["default"] = default
    elif not required:
        field_kwargs["default"] = None
    else:
        # required field with no default → use PydanticUndefined (ellipsis)
        field_kwargs["default"] = ...

    return python_type, Field(**field_kwargs)


def build_pydantic_from_schema(
    json_schema: dict[str, Any],
    model_name: str = "DynamicAnalyticsAppParams",
) -> type[BaseModel]:
    """Create and return a Pydantic BaseModel class from a JSON Schema dict.

    Supports: required fields, optional fields, defaults, numeric/string
    constraints, and ``anyOf: [type, null]`` patterns.
    """
    properties: dict[str, Any] = json_schema.get("properties") or {}
    required_fields: set[str] = set(json_schema.get("required") or [])

    field_definitions: dict[str, Any] = {}
    for field_name, prop_schema in properties.items():
        python_type, field_info = _build_field(
            prop_schema, required=(field_name in required_fields)
        )
        field_definitions[field_name] = (python_type, field_info)

    return create_model(model_name, **field_definitions)
