# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Validated, allowlisted contract for structured detection queries."""

import math
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

DetectionField = Literal[
    "id", "frame_id", "label", "confidence", "x", "y", "width", "height", "timestamp"
]
GroupField = Literal["frame_id", "label", "timestamp"]
NumericField = Literal["id", "frame_id", "confidence", "x", "y", "width", "height"]
FilterOperator = Literal[
    "eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "between",
    "contains", "starts_with",
]
Scalar = int | float | str

NUMERIC_FIELDS = {"id", "frame_id", "confidence", "x", "y", "width", "height"}
TEXT_FIELDS = {"label", "timestamp"}
COMPARISON_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte"}
SEQUENCE_OPERATORS = {"in", "not_in"}
TEXT_OPERATORS = {"contains", "starts_with"}
ALIAS_PATTERN = r"^[a-z][a-z0-9_]{0,31}$"


class QueryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QueryFilter(QueryModel):
    field: DetectionField
    operator: FilterOperator
    value: Scalar | list[Scalar]

    @model_validator(mode="after")
    def validate_filter(self):
        values = self.value if isinstance(self.value, list) else [self.value]
        if any(isinstance(value, bool) for value in values):
            raise ValueError("boolean filter values are not supported")
        if any(isinstance(value, float) and not math.isfinite(value) for value in values):
            raise ValueError("numeric filter values must be finite")
        if self.operator in SEQUENCE_OPERATORS:
            if not isinstance(self.value, list) or not 1 <= len(self.value) <= 100:
                raise ValueError(f"{self.operator} requires a list of 1 to 100 values")
        elif self.operator == "between":
            if not isinstance(self.value, list) or len(self.value) != 2:
                raise ValueError("between requires exactly two values")
        elif isinstance(self.value, list):
            raise ValueError(f"{self.operator} requires a scalar value")

        if self.field in NUMERIC_FIELDS:
            if self.operator in TEXT_OPERATORS:
                raise ValueError(f"{self.operator} is only valid for text fields")
            if any(not isinstance(value, (int, float)) for value in values):
                raise ValueError(f"{self.field} requires numeric filter values")
            if any(
                isinstance(value, int) and not -(2**63) <= value < 2**63
                for value in values
            ):
                raise ValueError("integer filter values must fit in a signed 64-bit integer")
            if self.field in {"id", "frame_id"}:
                if any(not isinstance(value, int) for value in values):
                    raise ValueError(f"{self.field} requires integer filter values")
        elif self.field in TEXT_FIELDS:
            if self.operator == "between":
                raise ValueError("between is only valid for numeric fields")
            if any(not isinstance(value, str) or len(value) > 256 for value in values):
                raise ValueError(f"{self.field} requires text values of at most 256 characters")
        return self


class SortSpec(QueryModel):
    field: DetectionField
    direction: Literal["asc", "desc"] = "asc"


class QueryBase(QueryModel):
    filters: list[QueryFilter] = Field(default_factory=list, max_length=20)


class ListQuery(QueryBase):
    operation: Literal["list"]
    fields: list[DetectionField] = Field(
        default_factory=lambda: [
            "id", "frame_id", "label", "confidence", "x", "y", "width", "height", "timestamp"
        ],
        min_length=1,
        max_length=9,
    )
    sort: list[SortSpec] = Field(
        default_factory=lambda: [SortSpec(field="id", direction="asc")],
        max_length=3,
    )
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0, le=10_000)

    @model_validator(mode="after")
    def validate_unique_fields(self):
        if len(set(self.fields)) != len(self.fields):
            raise ValueError("fields must be unique")
        if len({item.field for item in self.sort}) != len(self.sort):
            raise ValueError("sort fields must be unique")
        return self


class CountQuery(QueryBase):
    operation: Literal["count"]


class AggregateMetric(QueryModel):
    function: Literal["count", "avg", "min", "max", "sum"]
    field: NumericField | None = None
    alias: str = Field(pattern=ALIAS_PATTERN)

    @model_validator(mode="after")
    def validate_metric(self):
        if self.function == "count" and self.field is not None:
            raise ValueError("count does not accept a field")
        if self.function != "count" and self.field is None:
            raise ValueError(f"{self.function} requires a numeric field")
        return self


class AggregateQuery(QueryBase):
    operation: Literal["aggregate"]
    metrics: list[AggregateMetric] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_aliases(self):
        if len({metric.alias for metric in self.metrics}) != len(self.metrics):
            raise ValueError("metric aliases must be unique")
        return self


class GroupSortSpec(QueryModel):
    field: str = Field(pattern=ALIAS_PATTERN)
    direction: Literal["asc", "desc"] = "asc"


class GroupByQuery(QueryBase):
    operation: Literal["group_by"]
    group_by: list[GroupField] = Field(min_length=1, max_length=2)
    metrics: list[AggregateMetric] = Field(min_length=1, max_length=10)
    sort: list[GroupSortSpec] = Field(default_factory=list, max_length=3)
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0, le=10_000)

    @model_validator(mode="after")
    def validate_group_query(self):
        if len(set(self.group_by)) != len(self.group_by):
            raise ValueError("group_by fields must be unique")
        aliases = [metric.alias for metric in self.metrics]
        if len(set(aliases)) != len(aliases):
            raise ValueError("metric aliases must be unique")
        if set(aliases) & set(self.group_by):
            raise ValueError("metric aliases must not duplicate group_by fields")
        allowed_sort_fields = set(self.group_by) | set(aliases)
        if any(item.field not in allowed_sort_fields for item in self.sort):
            raise ValueError("group sort fields must be group_by fields or metric aliases")
        if len({item.field for item in self.sort}) != len(self.sort):
            raise ValueError("sort fields must be unique")
        return self


class FrameSortSpec(QueryModel):
    field: Literal[
        "frame_id", "detection_count", "avg_confidence", "min_confidence", "max_confidence"
    ]
    direction: Literal["asc", "desc"] = "asc"


class FramesQuery(QueryBase):
    operation: Literal["frames"]
    sort: list[FrameSortSpec] = Field(
        default_factory=lambda: [FrameSortSpec(field="frame_id", direction="asc")],
        max_length=3,
    )
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0, le=10_000)

    @model_validator(mode="after")
    def validate_sort(self):
        if len({item.field for item in self.sort}) != len(self.sort):
            raise ValueError("sort fields must be unique")
        return self


DetectionQuery = Annotated[
    Union[ListQuery, CountQuery, AggregateQuery, GroupByQuery, FramesQuery],
    Field(discriminator="operation"),
]


class QueryMetadata(QueryModel):
    operation: Literal["list", "count", "aggregate", "group_by", "frames"]
    returned: int = Field(ge=0)
    fields: list[str]
    limit: int | None = Field(default=None, ge=1, le=500)
    offset: int | None = Field(default=None, ge=0, le=10_000)
    has_more: bool = False
    grouped_by: list[str] = Field(default_factory=list)


class DetectionQueryResponse(QueryModel):
    data: list[dict[str, Scalar | None]]
    meta: QueryMetadata
