# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""DL Streamer Pipeline Server client — starts a bounded inference run on demand.

Detection is no longer kept perpetually running in the background: each "Run
Pipeline" action starts exactly one pipeline instance over the (finite) source
video, waits for it to reach a terminal state, and only then hands off to the
agent-reasoning stage — mirroring the reference CLI's "run inference once,
then reason once" model.
"""

import logging
import os
import time

import requests

log = logging.getLogger(__name__)

_DLSTREAMER_URL      = os.environ.get("DLSTREAMER_URL", "http://dlstreamer-pipeline-server:8554")
_PIPELINE_NAME       = os.environ.get("DLSTREAMER_PIPELINE_NAME", "pipeline_defect_detection")
_PIPELINE_GROUP      = os.environ.get("DLSTREAMER_PIPELINE_GROUP", "user_defined_pipelines")
_MQTT_TOPIC          = os.environ.get("MQTT_TOPIC", "apm/detections")
_VIDEOS_DIR          = os.environ.get("VIDEOS_DIR", "/app/videos")
# Path DL Streamer Pipeline Server sees for the same resources dir (its own mount).
_DLSTREAMER_VIDEOS_PATH = os.environ.get(
    "DLSTREAMER_VIDEOS_PATH", "/home/pipeline-server/resources/videos"
)
_TIMEOUT = 5

# Maps a UI-selectable device name to the pipeline definition that runs
# gvadetect on that device (see configs/pipeline-server-config.json).
_PIPELINE_NAME_BY_DEVICE = {
    "CPU": os.environ.get("DLSTREAMER_PIPELINE_NAME_CPU", "pipeline_defect_detection"),
    "GPU": os.environ.get("DLSTREAMER_PIPELINE_NAME_GPU", "pipeline_defect_detection_gpu"),
    "NPU": os.environ.get("DLSTREAMER_PIPELINE_NAME_NPU", "pipeline_defect_detection_npu"),
}

_NO_PROXY_HOSTS = {"no_proxy": "dlstreamer-pipeline-server,localhost,127.0.0.1"}

# Terminal states reported by the DL Streamer Pipeline Server's /pipelines/status.
_TERMINAL_STATES = {"COMPLETED", "ERROR", "ABORTED"}


def list_available_videos() -> list[str]:
    """List video filenames available under the shared resources/videos dir.

    Returns an empty list (rather than raising) if the directory is missing
    or unreadable, so callers can fall back to the pipeline's default source.
    """
    try:
        names = sorted(
            f for f in os.listdir(_VIDEOS_DIR)
            if f.lower().endswith((".mp4", ".avi", ".mkv", ".mov"))
        )
        return names
    except OSError as exc:
        log.warning("Could not list videos in %s: %s", _VIDEOS_DIR, exc)
        return []


class PipelineRunError(Exception):
    """Raised when the DL Streamer pipeline cannot be started or fails to complete."""


def _get_instance_status(instance_id: str) -> dict | None:
    """Find the status entry for a specific pipeline instance id."""
    try:
        r = requests.get(f"{_DLSTREAMER_URL}/pipelines/status", timeout=_TIMEOUT, proxies=_NO_PROXY_HOSTS)
        if r.status_code == 200:
            for p in r.json():
                if p.get("id") == instance_id:
                    return p
    except Exception as exc:
        log.warning("Could not query DL Streamer pipeline status: %s", exc)
    return None


def _start_pipeline(device: str = "CPU", video_filename: str | None = None) -> str:
    """Start a new pipeline instance. Returns the instance id, or raises PipelineRunError."""
    pipeline_name = _PIPELINE_NAME_BY_DEVICE.get(device.upper(), _PIPELINE_NAME) if device else _PIPELINE_NAME

    payload = {
        "destination": {
            "metadata": {
                "type": "mqtt",
                "topic": _MQTT_TOPIC,
            }
        }
    }
    if video_filename:
        payload["source"] = {
            "uri": f"file://{_DLSTREAMER_VIDEOS_PATH}/{video_filename}",
            "type": "uri",
        }

    try:
        r = requests.post(
            f"{_DLSTREAMER_URL}/pipelines/{_PIPELINE_GROUP}/{pipeline_name}",
            json=payload,
            timeout=_TIMEOUT,
            proxies=_NO_PROXY_HOSTS,
        )
        if r.status_code in (200, 201):
            try:
                instance_id = r.json()
            except ValueError:
                instance_id = r.text
            if isinstance(instance_id, str):
                instance_id = instance_id.strip().strip('"')
            log.info("DL Streamer pipeline '%s' started (instance: %s)", pipeline_name, instance_id)
            return instance_id
        raise PipelineRunError(f"Failed to start pipeline: {r.status_code} {r.text}")
    except PipelineRunError:
        raise
    except Exception as exc:
        raise PipelineRunError(f"Could not reach DL Streamer Pipeline Server: {exc}") from exc


def run_pipeline_to_completion(
    device: str = "CPU",
    video_filename: str | None = None,
    poll_interval: float = 2.0,
    timeout: float = 600.0,
) -> dict:
    """Start the pipeline and block until it reaches a terminal state.

    ``device`` selects which pipeline definition (CPU/GPU/NPU) to run.
    ``video_filename`` optionally overrides the source video, relative to the
    shared resources/videos directory; when omitted, the pipeline's own
    default source (sample.mp4) is used.

    Returns the final status dict (``{"id", "state", "avg_fps", "elapsed_time", ...}``).
    Raises ``PipelineRunError`` if the pipeline cannot be started, or times out
    without reaching a terminal state.
    """
    instance_id = _start_pipeline(device=device, video_filename=video_filename)

    deadline = time.monotonic() + timeout
    last_status: dict | None = None
    while time.monotonic() < deadline:
        status = _get_instance_status(instance_id)
        if status is not None:
            last_status = status
            state = status.get("state")
            if state in _TERMINAL_STATES:
                log.info(
                    "DL Streamer pipeline %s finished: state=%s elapsed=%.1fs",
                    instance_id, state, status.get("elapsed_time", 0.0),
                )
                if state != "COMPLETED":
                    raise PipelineRunError(
                        f"Pipeline {instance_id} ended in state={state} "
                        f"(device={device}, video={video_filename or '<default>'}): {status}"
                    )
                return status
        time.sleep(poll_interval)

    raise PipelineRunError(
        f"Pipeline {instance_id} did not reach a terminal state within {timeout}s "
        f"(last known status: {last_status})"
    )

