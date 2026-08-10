# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
SQLite client for persisting and querying defect detections.
"""

import sqlite3
import logging
import os
from typing import Optional

from src.query_models import (
    AggregateMetric,
    AggregateQuery,
    CountQuery,
    DetectionQuery,
    FramesQuery,
    GroupByQuery,
    ListQuery,
    QueryFilter,
)

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS detections (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    frame_id  INTEGER NOT NULL,
    label     TEXT    NOT NULL,
    confidence REAL   NOT NULL,
    x         REAL    NOT NULL,
    y         REAL    NOT NULL,
    width     REAL    NOT NULL,
    height    REAL    NOT NULL,
    timestamp TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_frame_id   ON detections(frame_id);
CREATE INDEX IF NOT EXISTS idx_label      ON detections(label);
CREATE INDEX IF NOT EXISTS idx_confidence ON detections(confidence);
"""

FIELD_SQL = {
    "id": "id",
    "frame_id": "frame_id",
    "label": "label",
    "confidence": "confidence",
    "x": "x",
    "y": "y",
    "width": "width",
    "height": "height",
    "timestamp": "timestamp",
}
FRAME_FIELD_SQL = {
    "frame_id": "frame_id",
    "detection_count": "detection_count",
    "avg_confidence": "avg_confidence",
    "min_confidence": "min_confidence",
    "max_confidence": "max_confidence",
}
OPERATOR_SQL = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
}
AGGREGATE_SQL = {
    "count": "COUNT(*)",
    "avg": "AVG({field})",
    "min": "MIN({field})",
    "max": "MAX({field})",
    "sum": "SUM({field})",
}


class SQLiteClient:
    """Thread-safe SQLite client for detection persistence."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True) if os.path.dirname(db_path) else None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript(SCHEMA)
        logger.info("Database initialised at %s", self.db_path)

    def insert_detection(self, frame_id: int, label: str, confidence: float,
                         x: float, y: float, width: float, height: float) -> int:
        sql = """INSERT INTO detections (frame_id, label, confidence, x, y, width, height)
                 VALUES (?, ?, ?, ?, ?, ?, ?)"""
        with self._get_conn() as conn:
            cursor = conn.execute(sql, (frame_id, label, confidence, x, y, width, height))
            return cursor.lastrowid

    def insert_many(self, records: list[dict]) -> int:
        """Bulk insert detections. Each dict must have frame_id, label, confidence, x, y, width, height."""
        sql = """INSERT INTO detections (frame_id, label, confidence, x, y, width, height)
                 VALUES (:frame_id, :label, :confidence, :x, :y, :width, :height)"""
        with self._get_conn() as conn:
            conn.executemany(sql, records)
            return len(records)

    def get_detections(self, label: Optional[str] = None,
                       min_confidence: Optional[float] = None,
                       min_id: Optional[int] = None,
                       max_id: Optional[int] = None,
                       limit: Optional[int] = None) -> list[dict]:
        conditions = []
        params: list = []
        if label:
            conditions.append("label = ?")
            params.append(label)
        if min_confidence is not None:
            conditions.append("confidence >= ?")
            params.append(min_confidence)
        if min_id is not None:
            conditions.append("id > ?")
            params.append(min_id)
        if max_id is not None:
            conditions.append("id <= ?")
            params.append(max_id)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        limit_clause = f"LIMIT {int(limit)}" if limit else ""
        sql = f"SELECT * FROM detections {where} ORDER BY confidence DESC {limit_clause}"

        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _compile_filters(filters: list[QueryFilter]) -> tuple[str, list]:
        conditions: list[str] = []
        params: list = []
        for item in filters:
            field = FIELD_SQL[item.field]
            if item.operator in OPERATOR_SQL:
                conditions.append(f"{field} {OPERATOR_SQL[item.operator]} ?")
                params.append(item.value)
            elif item.operator in {"in", "not_in"}:
                values = item.value
                placeholders = ", ".join("?" for _ in values)
                keyword = "IN" if item.operator == "in" else "NOT IN"
                conditions.append(f"{field} {keyword} ({placeholders})")
                params.extend(values)
            elif item.operator == "between":
                conditions.append(f"{field} BETWEEN ? AND ?")
                params.extend(item.value)
            elif item.operator in {"contains", "starts_with"}:
                escaped = str(item.value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                pattern = f"%{escaped}%" if item.operator == "contains" else f"{escaped}%"
                conditions.append(f"{field} LIKE ? ESCAPE '\\'")
                params.append(pattern)
            else:  # Models reject unknown operators before this boundary.
                raise ValueError("Unsupported filter operator")
        return (f" WHERE {' AND '.join(conditions)}" if conditions else ""), params

    @staticmethod
    def _compile_metrics(metrics: list[AggregateMetric]) -> list[str]:
        expressions = []
        for metric in metrics:
            field = FIELD_SQL[metric.field] if metric.field else None
            expression = AGGREGATE_SQL[metric.function]
            if field:
                expression = expression.format(field=field)
            expressions.append(f'{expression} AS "{metric.alias}"')
        return expressions

    def query_detections(self, query: DetectionQuery) -> dict:
        """Execute a validated structured query without accepting raw SQL fragments."""
        where, params = self._compile_filters(query.filters)
        limit = None
        offset = None
        grouped_by: list[str] = []

        if isinstance(query, ListQuery):
            fields = list(query.fields)
            select = ", ".join(FIELD_SQL[field] for field in fields)
            order = ", ".join(
                f"{FIELD_SQL[item.field]} {item.direction.upper()}" for item in query.sort
            )
            sql = f"SELECT {select} FROM detections{where}"
            if order:
                sql += f" ORDER BY {order}"
            limit, offset = query.limit, query.offset
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit + 1, offset])
        elif isinstance(query, CountQuery):
            fields = ["count"]
            sql = f"SELECT COUNT(*) AS count FROM detections{where}"
        elif isinstance(query, AggregateQuery):
            fields = [metric.alias for metric in query.metrics]
            sql = f"SELECT {', '.join(self._compile_metrics(query.metrics))} FROM detections{where}"
        elif isinstance(query, GroupByQuery):
            grouped_by = list(query.group_by)
            fields = grouped_by + [metric.alias for metric in query.metrics]
            group_fields = ", ".join(FIELD_SQL[field] for field in query.group_by)
            selections = [FIELD_SQL[field] for field in query.group_by]
            selections.extend(self._compile_metrics(query.metrics))
            sql = (
                f"SELECT {', '.join(selections)} FROM detections{where} "
                f"GROUP BY {group_fields}"
            )
            if query.sort:
                allowed_sort_sql = {field: FIELD_SQL[field] for field in query.group_by}
                allowed_sort_sql.update({metric.alias: f'"{metric.alias}"' for metric in query.metrics})
                sql += " ORDER BY " + ", ".join(
                    f"{allowed_sort_sql[item.field]} {item.direction.upper()}" for item in query.sort
                )
            limit, offset = query.limit, query.offset
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit + 1, offset])
        elif isinstance(query, FramesQuery):
            grouped_by = ["frame_id"]
            fields = [
                "frame_id", "detection_count", "avg_confidence",
                "min_confidence", "max_confidence",
            ]
            sql = (
                "SELECT frame_id, COUNT(*) AS detection_count, "
                "AVG(confidence) AS avg_confidence, MIN(confidence) AS min_confidence, "
                f"MAX(confidence) AS max_confidence FROM detections{where} GROUP BY frame_id"
            )
            if query.sort:
                sql += " ORDER BY " + ", ".join(
                    f"{FRAME_FIELD_SQL[item.field]} {item.direction.upper()}" for item in query.sort
                )
            limit, offset = query.limit, query.offset
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit + 1, offset])
        else:
            raise ValueError("Unsupported query operation")

        with self._get_conn() as conn:
            rows = [dict(row) for row in conn.execute(sql, params).fetchall()]

        has_more = limit is not None and len(rows) > limit
        if has_more:
            rows = rows[:limit]
        return {
            "data": rows,
            "meta": {
                "operation": query.operation,
                "returned": len(rows),
                "fields": fields,
                "limit": limit,
                "offset": offset,
                "has_more": has_more,
                "grouped_by": grouped_by,
            },
        }

    def get_summary(self, min_id: Optional[int] = None,
                    max_id: Optional[int] = None) -> dict:
        """Return per-class detection counts and confidence stats.

        Optionally scoped to a detection-id window (id > min_id and id <= max_id)
        so callers can summarize only the detections accumulated since a previous
        analysis run, instead of always aggregating the entire (potentially
        unbounded, ever-growing) detection history.
        """
        conditions = []
        params: list = []
        if min_id is not None:
            conditions.append("id > ?")
            params.append(min_id)
        if max_id is not None:
            conditions.append("id <= ?")
            params.append(max_id)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        sql = f"""
        SELECT label,
               COUNT(*)          AS count,
               AVG(confidence)   AS avg_confidence,
               MAX(confidence)   AS max_confidence,
               MIN(confidence)   AS min_confidence
        FROM detections
        {where}
        GROUP BY label
        ORDER BY count DESC
        """
        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {"by_class": [dict(r) for r in rows]}

    def get_max_id(self) -> int:
        """Return the highest detection id currently stored (0 if empty)."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM detections").fetchone()
        return int(row[0])

    def count(self, min_id: Optional[int] = None, max_id: Optional[int] = None) -> int:
        conditions = []
        params: list = []
        if min_id is not None:
            conditions.append("id > ?")
            params.append(min_id)
        if max_id is not None:
            conditions.append("id <= ?")
            params.append(max_id)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        with self._get_conn() as conn:
            return conn.execute(f"SELECT COUNT(*) FROM detections {where}", params).fetchone()[0]

    def clear(self):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM detections")
        logger.info("Cleared all detections from database")
