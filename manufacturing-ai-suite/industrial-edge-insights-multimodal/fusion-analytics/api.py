#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""
Fusion Analytics REST API

Provides HTTP endpoints for querying vision weld classification results
stored in InfluxDB. Separated from the MQTT fusion loop for clarity.
"""

import os
import re
import time
import logging

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
APM_API_KEY = os.getenv("APM_API_KEY", "")
API_PORT = int(os.getenv("API_PORT", "8080"))
FUSION_MEASUREMENT = "fusion_result"

# Label allow-list: only alphanumeric, underscore, hyphen, dot, and space
_SAFE_LABEL_RE = re.compile(r"^[A-Za-z0-9_\-\. ]+$")

_api_start_time = time.time()
_api_request_count = 0

# Shared InfluxDB client — set by fusion.py at startup via set_influx_client()
_influx_client = None


def set_influx_client(client) -> None:
    """Called by fusion main() after InfluxDB is initialized."""
    global _influx_client
    _influx_client = client


# ── App ────────────────────────────────────────────────────────────────────────
api_app = FastAPI(
    title="Fusion Analytics API",
    description="REST API for querying fusion analytics results stored in InfluxDB",
    version="1.0.0",
)


# ── Helpers ────────────────────────────────────────────────────────────────────
def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Enforce API key auth for mutating endpoints."""
    if not APM_API_KEY:
        return
    if x_api_key != APM_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _influx_points(query: str) -> list:
    """Execute an InfluxQL query and return results as a list of dicts."""
    if _influx_client is None:
        raise HTTPException(status_code=503, detail="InfluxDB client not initialized")
    try:
        result = _influx_client.query(query)
        data = []
        for (measurement, tags), points in result.items():
            fc = (tags or {}).get("fusion_classification", "UNKNOWN")
            for point in points:
                data.append({"fusion_classification": fc, **point})
        return data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Routes ─────────────────────────────────────────────────────────────────────
@api_app.get("/health")
def health():
    """Health check: verify InfluxDB connectivity and report stored detection count."""
    if _influx_client is None:
        raise HTTPException(status_code=503, detail="InfluxDB client not initialized")
    try:
        _influx_client.ping()
        points = _influx_points(f"SELECT count(fused_decision) as count FROM \"{FUSION_MEASUREMENT}\"")
        count = points[0].get("count", 0) if points else 0
        return {"status": "ok", "detections_count": count}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@api_app.get("/detections")
def get_detections(
    label: str | None = Query(None, description="Filter by label"),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0, description="Minimum confidence threshold (0-1)"),
    min_id: int | None = Query(None, ge=0, description="Row offset — skip the first min_id results (ordered by time)"),
    max_id: int | None = Query(None, ge=0, description="Upper row bound — combined with min_id to derive LIMIT"),
    limit: int | None = Query(None, ge=1),
):
    """Query vision weld classification results with optional filters."""
    global _api_request_count
    _api_request_count += 1

    logger.info(f"Detections request: label={label}, min_confidence={min_confidence}, min_id={min_id}, max_id={max_id}, limit={limit}")
    conditions = []
    if label is not None:
        conditions.append(f"fusion_classification = '{label}'")
    if min_confidence is not None:
        conditions.append(f"fusion_confidence >= {min_confidence}")
    if min_id is not None:
        conditions.append(f"time > {min_id}")
    if max_id is not None:
        conditions.append(f"time <= {max_id}")

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    limit_clause = f" LIMIT {limit}" if limit else ""
    query = f"SELECT fused_decision, fusion_classification as label, fusion_confidence as confidence, mode, timeseries_anomaly, timeseries_classification, timeseries_confidence, timeseries_timestamp, ts_anomaly, vision_anomaly, vision_classification, vision_confidence, vision_rtsp_ts_diff_ms, vision_timestamp FROM \"{FUSION_MEASUREMENT}\"{where_clause} ORDER BY time DESC{limit_clause}"
    return _influx_points(query)


@api_app.get("/detections/summary")
def get_summary(
    min_id: int | None = Query(None, ge=0, description="Row offset for scoping the summary window"),
    max_id: int | None = Query(None, ge=0, description="Upper row bound for the summary window"),
):
    """Return per-class statistics aggregated from stored vision weld classification results."""

    logger.info(f"Summary request: min_id={min_id}, max_id={max_id}")
    conditions = []
    if min_id is not None:
        conditions.append(f"time > {min_id}")
    if max_id is not None:
        conditions.append(f"time <= {max_id}")

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT COUNT(fusion_confidence) as count, MEAN(fusion_confidence) as avg_confidence, MAX(fusion_confidence) as max_confidence, MIN(fusion_confidence) as min_confidence FROM \"{FUSION_MEASUREMENT}\"{where_clause} GROUP BY fusion_classification ORDER BY time ASC"
    points = _influx_points(query)

    # SELECT COUNT("fusion_confidence"), MEAN("fusion_confidence") FROM "fusion_result" GROUP BY "fusion_classification"

    logger.debug(f"Summary query: {query} data points: {points}")
    summary: dict[str, dict] = {}
    for p in points:
        label = "unknown"
        try:
            label = p.get("fusion_classification", "unknown")
        except (ValueError, KeyError, IndexError, TypeError):
            pass

        if label not in summary:
            summary[label] = {"count": 0, "avg_confidence": 0.0, "max_confidence": 0.0, "min_confidence": 0.0, "label": "unknown"}
        summary[label]["count"] = int(p.get("count") or 0)
        summary[label]["avg_confidence"] = float(p.get("avg_confidence") or 0.0)
        summary[label]["max_confidence"] = float(p.get("max_confidence") or 0.0)
        summary[label]["min_confidence"] = float(p.get("min_confidence") or 0.0)
        summary[label]["label"] = label
        summary[label]["fusion_mode"] = str(os.getenv("FUSION_MODE", "OR"))
    return summary


@api_app.get("/detections/max_id")
def get_max_id():
    """Return total stored detection count used as a watermark by consumers."""
    points = _influx_points(f"SELECT count(fused_decision) AS count,time FROM \"{FUSION_MEASUREMENT}\" ORDER BY time DESC LIMIT 1")
    max_id = points[0].get("time", 0) if points else 0
    total_count = points[0].get("count", 0) if points else 0
    return {"max_id": max_id, "total_count": total_count}

@api_app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    """Expose Prometheus-style metrics."""
    global _api_start_time, _api_request_count
    uptime = time.time() - _api_start_time
    count = 0
    if _influx_client is not None:
        try:
            points = list(_influx_client.query(f"SELECT count(fused_decision) as count FROM \"{FUSION_MEASUREMENT}\"").get_points())
            count = points[0].get("count", 0) if points else 0
        except Exception:
            pass
    return (
        f"# HELP fusion_detections_total Total fusion results stored\n"
        f"# TYPE fusion_detections_total gauge\n"
        f"fusion_detections_total {count}\n"
        f"# HELP fusion_requests_total Total HTTP requests handled\n"
        f"# TYPE fusion_requests_total counter\n"
        f"fusion_requests_total {_api_request_count}\n"
        f"# HELP fusion_uptime_seconds Service uptime in seconds\n"
        f"# TYPE fusion_uptime_seconds gauge\n"
        f"fusion_uptime_seconds {uptime:.1f}\n"
    )
