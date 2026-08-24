# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Per-stage aggregation of the raw utilization time series.

The collectors under ``monitoring/scripts`` write one undifferentiated CSV row
per sampling interval for the whole session. This module slices those series by
pipeline stage (ASR / Summary / Mind map / Video) and reports, for each stage:

    Time Range, Memory Util(GB), CPU Util(%), GPU 3D Util(%),
    GPU Compute Util(%), GPU Decode Util(%), GPU Video Process Util(%),
    NPU Util(%)

What each stage window covers in the running product:

``ASR``       ``/transcribe`` -> ``Pipeline.run_transcription``: FFmpeg
              chunking plus the ASR model transcribing each chunk.
``Summary``   ``/summarize`` -> ``Pipeline.run_summarizer``: the summarizer LLM
              streaming tokens over the transcript (and the board OCR text).
``Mind map``  ``/mindmap`` -> ``Pipeline.run_mindmap``: one text_gen/VLM call
              turning the summary into a jsMind tree.
``Video``     ``/start-video-analytics-pipeline``: the front/back/content
              GStreamer subprocesses, from the first launch until the last
              pipeline's monitor thread observes it exit.

Stage windows come from the ``[STAGE]`` markers emitted by
``utils.time_marker.mark``: every marker is appended to
``<session>/utilization_logs/stage_timeline.csv``, and those carrying a
``start``/``end`` boundary delimit the aggregation windows. A stage spans its
earliest ``start`` boundary to its latest ``end`` boundary, so the ``Video``
stage covers all three concurrent VA pipelines as one window. Markers recorded
with the ``info`` boundary (API entry/exit, uploads, pipeline construction, VA
launch and board OCR details) are kept in the timeline for end-to-end timing
analysis but do not move any window.

Two properties of the report follow from the real pipeline flow and are worth
keeping in mind when reading it:

* **The windows overlap.** ``Video`` is started alongside ``ASR`` and keeps
  running through ``Summary`` and ``Mind map``, so its window contains all
  three. The three audio stages are sequential and do not overlap each other.
* **The collectors are system wide.** A row says what the machine was doing
  during that stage, not what the stage alone consumed — the GPU decode and
  video-process figures during ``ASR`` are the concurrent VA pipelines, not the
  ASR model. ``GPU Compute Util(%)`` is where OpenVINO ``device: GPU``
  inference lands (see ``scripts/windows/gpu_engines.py``), so it is the column
  that tracks the summarizer and mind-map models.

``stage_metrics.csv`` is refreshed as soon as each stage closes, so the report
exists even when the process never reaches ``monitor.stop_monitoring`` (the
backend being killed, or the UI never calling ``/stop-monitoring``).
"""

import csv
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"

TIMELINE_FILE = "stage_timeline.csv"
STAGE_METRICS_FILE = "stage_metrics.csv"

# Stage display names. Markers reference these verbatim.
STAGE_ASR = "ASR"
STAGE_SUMMARY = "Summary"
STAGE_MINDMAP = "Mind map"
STAGE_VIDEO = "Video"

# Report order; stages with no recorded window are omitted from the output.
STAGE_ORDER = [STAGE_ASR, STAGE_SUMMARY, STAGE_MINDMAP, STAGE_VIDEO]

# Timeline boundaries. start/end delimit a stage window; info is a milestone
# that is recorded for timing analysis only.
BOUNDARY_START = "start"
BOUNDARY_END = "end"
BOUNDARY_INFO = "info"
BOUNDARIES = (BOUNDARY_START, BOUNDARY_END, BOUNDARY_INFO)

# metric key -> (csv file written by the collector, column header, unit label)
METRIC_SOURCES = {
    "memory_util_gb": ("memory_metrics.csv", "used_gb", "GB"),
    "cpu_util_percent": ("cpu_utilization.csv", "total_cpu_utilization", "%"),
    "gpu_3d_util_percent": ("gpu_metrics.csv", "3D_utilization_percent", "%"),
    "gpu_compute_util_percent": ("gpu_metrics.csv", "Compute_utilization_percent", "%"),
    "gpu_decode_util_percent": ("gpu_metrics.csv", "VideoDecode_utilization_percent", "%"),
    "gpu_video_process_util_percent": (
        "gpu_metrics.csv",
        "VideoProcessing_utilization_percent",
        "%",
    ),
    "npu_util_percent": ("npu_metrics.csv", "total_npu_utilization", "%"),
}

# Column headers for the exported CSV / rendered table, in the requested order.
REPORT_COLUMNS = [
    ("stage", "Stage"),
    ("time_range", "Time Range"),
    ("duration_sec", "Duration(s)"),
    ("memory_util_gb", "Memory Util(GB)"),
    ("cpu_util_percent", "CPU Util(%)"),
    ("gpu_3d_util_percent", "GPU 3D Util(%)"),
    ("gpu_compute_util_percent", "GPU Compute Util(%)"),
    ("gpu_decode_util_percent", "GPU Decode Util(%)"),
    ("gpu_video_process_util_percent", "GPU Video Process Util(%)"),
    ("npu_util_percent", "NPU Util(%)"),
]

_timeline_lock = threading.Lock()
# stage_metrics.csv is rewritten whole; serialize writers so two stages ending
# in the same second cannot truncate each other's output.
_export_lock = threading.RLock()


# ── stage timeline recording ────────────────────────────────────────────────


def timeline_path(metrics_logs: str) -> str:
    return os.path.join(metrics_logs, TIMELINE_FILE)


def record_stage_event(
    metrics_logs: str, stage: str, boundary: str, event: str, timestamp: str
) -> None:
    """Append one marker to the session's stage timeline.

    ``boundary`` is ``"start"``/``"end"`` to delimit a stage window, or
    ``"info"`` for a milestone that is only being timestamped. ``stage`` may be
    empty for milestones that belong to no particular stage. ``event`` keeps the
    original marker text so per-pipeline detail (e.g. which VA pipeline ended)
    survives even though several events collapse into one stage window.
    """
    if boundary not in BOUNDARIES:
        logger.warning("Ignoring stage event '%s': bad boundary '%s'", event, boundary)
        return

    path = timeline_path(metrics_logs)
    try:
        with _timeline_lock:
            os.makedirs(metrics_logs, exist_ok=True)
            new_file = not os.path.exists(path)
            with open(path, "a", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                if new_file:
                    writer.writerow(["timestamp", "stage", "boundary", "event"])
                writer.writerow([timestamp, stage, boundary, event])
                fh.flush()
    except Exception as e:
        # Instrumentation must never break the pipeline it measures.
        logger.error("Failed to record stage event '%s': %s", event, e)
        return

    # A stage that just closed is fully summarizable, so refresh the report now
    # rather than waiting for stop_monitoring() — which the UI may never call.
    if boundary == BOUNDARY_END:
        export_stage_metrics(metrics_logs, log_table=False)


# ── aggregation ────────────────────────────────────────────────────────────


def _parse(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts.strip())
    except Exception:
        return None


def _format(ts: datetime) -> str:
    """Render ISO local time with millisecond precision."""
    return ts.strftime(TIME_FORMAT)[:-3]


def _read_windows(metrics_logs: str) -> Dict[str, Dict]:
    """Collapse the stage timeline into one {start, end} window per stage.

    Only ``start``/``end`` rows delimit a window; ``info`` rows are timestamps
    recorded for reference and are skipped here.
    """
    path = timeline_path(metrics_logs)
    if not os.path.exists(path):
        return {}

    windows: Dict[str, Dict] = {}
    try:
        # Under the append lock: markers arrive from request and VA monitor
        # threads, so an unlocked read could see a half-written row.
        with _timeline_lock, open(path, "r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                stage = (row.get("stage") or "").strip()
                boundary = (row.get("boundary") or "").strip()
                stamp = _parse(row.get("timestamp") or "")
                if not stage or stamp is None:
                    continue
                if boundary not in (BOUNDARY_START, BOUNDARY_END):
                    continue

                win = windows.setdefault(stage, {"start": None, "end": None})
                if boundary == BOUNDARY_START:
                    if win["start"] is None or stamp < win["start"]:
                        win["start"] = stamp
                else:
                    if win["end"] is None or stamp > win["end"]:
                        win["end"] = stamp
    except Exception as e:
        logger.error("Failed to read stage timeline %s: %s", path, e)
        return {}

    return {s: w for s, w in windows.items() if w["start"] is not None}


def _read_series(metrics_logs: str, file_name: str, column: str) -> List[tuple]:
    """Return [(datetime, float)] for one column of one collector CSV."""
    path = os.path.join(metrics_logs, file_name)
    if not os.path.exists(path):
        return []

    series = []
    try:
        with open(path, "r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None or column not in reader.fieldnames:
                logger.warning("Column '%s' not found in %s", column, path)
                return []
            for row in reader:
                stamp = _parse(row.get("timestamp") or "")
                if stamp is None:
                    continue
                try:
                    series.append((stamp, float(row[column])))
                except (TypeError, ValueError):
                    continue
    except Exception as e:
        logger.error("Failed to read %s: %s", path, e)
        return []

    return series


def _sampling_gap(series: List[tuple]) -> Optional[timedelta]:
    """Median interval between consecutive samples of a collector series."""
    if len(series) < 2:
        return None
    gaps = sorted(
        (series[i][0] - series[i - 1][0]).total_seconds()
        for i in range(1, len(series))
    )
    median = gaps[len(gaps) // 2]
    return timedelta(seconds=median) if median > 0 else None


def _summarize(series: List[tuple], start: datetime, end: datetime) -> Dict:
    """Average / peak of the samples falling inside [start, end]."""
    values = [v for ts, v in series if start <= ts <= end]

    if not values:
        # A stage that ran for less than one sampling interval can fall between
        # two samples. Widen the window by one interval and use the neighbouring
        # samples rather than reporting n/a for a stage that really did run.
        gap = _sampling_gap(series)
        if gap is not None:
            values = [v for ts, v in series if start - gap <= ts <= end + gap]

    if not values:
        return {"avg": None, "max": None, "samples": 0}
    return {
        "avg": round(sum(values) / len(values), 2),
        "max": round(max(values), 2),
        "samples": len(values),
    }


def get_stage_metrics(metrics_logs: str = "./logs") -> Dict:
    """Aggregate every collected metric over each recorded stage window.

    A stage whose ``end`` boundary has not been recorded yet is reported as
    ``in_progress`` and aggregated up to the newest sample the collectors have
    written — not up to the wall clock, so a stage left open by a crash or a
    client disconnect cannot keep inflating its own duration.
    """
    windows = _read_windows(metrics_logs)
    if not windows:
        logger.info("No stage timeline found in %s — nothing to aggregate.", metrics_logs)
        return {"stages": []}

    # Read each collector column once, not once per stage.
    series_cache = {
        key: _read_series(metrics_logs, file_name, column)
        for key, (file_name, column, _unit) in METRIC_SOURCES.items()
    }

    last_sample = max(
        (ts for series in series_cache.values() for ts, _v in series), default=None
    )
    now = datetime.now()
    ordered = [s for s in STAGE_ORDER if s in windows]
    ordered += sorted(s for s in windows if s not in STAGE_ORDER)

    stages = []
    for stage in ordered:
        win = windows[stage]
        start = win["start"]
        end = win["end"]
        in_progress = end is None
        if end is not None:
            effective_end = end
        elif last_sample is not None:
            effective_end = max(last_sample, start)
        else:
            effective_end = now

        entry = {
            "stage": stage,
            "start": _format(start),
            "end": _format(end) if end else None,
            "time_range": "{} ~ {}".format(
                _format(start),
                _format(end) if end else "in progress",
            ),
            "duration_sec": round((effective_end - start).total_seconds(), 1),
            "in_progress": in_progress,
        }

        for key, (_file_name, _column, unit) in METRIC_SOURCES.items():
            summary = _summarize(series_cache[key], start, effective_end)
            summary["unit"] = unit
            entry[key] = summary

        stages.append(entry)

    return {"stages": stages}


# ── export / rendering ─────────────────────────────────────────────────────


def _cell(entry: Dict, key: str) -> str:
    """Render one report cell: scalars as-is, metrics as ``avg (peak max)``."""
    value = entry.get(key)
    if isinstance(value, dict):
        if value.get("avg") is None:
            return "n/a"
        return f"{value['avg']} (max {value['max']})"
    return "" if value is None else str(value)


def save_stage_metrics(metrics_logs: str, report: Optional[Dict] = None) -> Optional[str]:
    """Write the aggregated table to ``stage_metrics.csv``; return its path."""
    report = report if report is not None else get_stage_metrics(metrics_logs)
    stages = report.get("stages") or []
    if not stages:
        return None

    path = os.path.join(metrics_logs, STAGE_METRICS_FILE)
    try:
        with _export_lock:
            os.makedirs(metrics_logs, exist_ok=True)
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow([header for _key, header in REPORT_COLUMNS])
                for entry in stages:
                    writer.writerow(
                        [_cell(entry, key) for key, _header in REPORT_COLUMNS]
                    )
        return path
    except Exception as e:
        logger.error("Failed to write %s: %s", path, e)
        return None


def export_stage_metrics(
    metrics_logs: str = "./logs",
    report: Optional[Dict] = None,
    log_table: bool = True,
) -> Dict:
    """Aggregate, write ``stage_metrics.csv`` and return the report.

    The single entry point for producing the report: used by the periodic
    refresh on stage completion, by ``monitor.stop_monitoring`` and by the
    ``/stage-metrics`` endpoint. Never raises — instrumentation must not break
    the pipeline it measures.
    """
    try:
        with _export_lock:
            report = report if report is not None else get_stage_metrics(metrics_logs)
            if not report.get("stages"):
                return report
            report["exported_to"] = save_stage_metrics(metrics_logs, report)
            if log_table:
                logger.info(
                    "Per-stage utilization metrics:\n%s",
                    render_stage_metrics_table(report),
                )
            return report
    except Exception as e:
        logger.error("Failed to export stage metrics from %s: %s", metrics_logs, e)
        return report if isinstance(report, dict) else {"stages": []}


def render_stage_metrics_table(report: Optional[Dict] = None, metrics_logs: str = "./logs") -> str:
    """Render the aggregated table as aligned plain text (for logs / CLI)."""
    report = report if report is not None else get_stage_metrics(metrics_logs)
    stages = report.get("stages") or []
    if not stages:
        return "No stage metrics available."

    headers = [header for _key, header in REPORT_COLUMNS]
    rows = [[_cell(entry, key) for key, _header in REPORT_COLUMNS] for entry in stages]

    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))
    ]
    sep = "-+-".join("-" * w for w in widths)
    lines = [" | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)), sep]
    lines += [" | ".join(c.ljust(widths[i]) for i, c in enumerate(row)) for row in rows]
    return "\n".join(lines)
