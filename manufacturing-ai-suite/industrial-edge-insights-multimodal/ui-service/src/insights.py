# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Fusion analytics and weld explanation routes served by the Agentic UI."""

import base64
import datetime
import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import Annotated, Any
from urllib.request import urlopen

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from influxdb import InfluxDBClient
from openai import OpenAI
from pydantic import BaseModel, Field, StringConstraints, field_validator

log = logging.getLogger(__name__)
router = APIRouter(prefix="/insights-ui")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

FusionTimestamp = Annotated[
    str,
    StringConstraints(
        min_length=20,
        max_length=35,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$",
    ),
]


class ExplainRequest(BaseModel):
    """A single ISO-8601 fusion result selection from the workbench."""

    selected_times: list[FusionTimestamp] = Field(min_length=1, max_length=1)

    @field_validator("selected_times")
    @classmethod
    def validate_selected_times(cls, selected_times: list[str]) -> list[str]:
        for time_str in selected_times:
            try:
                datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("selected_times must contain valid ISO-8601 timestamps") from exc
        return selected_times


vllm_client = OpenAI(
    base_url=f"http://{os.getenv('VLLM_HOST', 'vllm-server')}:{os.getenv('VLLM_PORT', '8000')}/v1",
    api_key="EMPTY",
)


def get_seaweed_public_image_base_path() -> str:
    """Return the SeaweedFS path used to download weld images for the model."""
    return (
        f"{os.getenv('OBJECT_STORE_URL', 'http://seaweedfs-filer:8888')}/buckets/"
        f"{os.getenv('BUCKET_NAME', 'dlstreamer-pipeline-results/weld-defect-classification')}"
    ).rstrip("/")


def build_image_url(img_handle: str) -> str:
    return f"{get_seaweed_public_image_base_path()}/{img_handle}.jpg"


def build_image_data_url(image_url: str) -> str | None:
    """Download an image and return it as a base64 data URL for vLLM."""
    try:
        with urlopen(image_url, timeout=10) as response:  # nosec B310
            image_bytes = response.read()
            header_mime = response.headers.get_content_type()

        mime_type = header_mime if header_mime and header_mime != "application/octet-stream" else None
        if not mime_type:
            guessed_mime, _ = mimetypes.guess_type(image_url)
            mime_type = guessed_mime or "image/jpeg"

        return f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"
    except Exception:  # noqa: BLE001
        log.warning("Unable to load image %s", image_url, exc_info=True)
        return None


def get_query_prompt() -> dict[str, Any]:
    """Load the weld-quality system prompt from the UI image."""
    with Path(__file__).with_name("system_prompt.json").open(encoding="utf-8") as prompt_file:
        return json.load(prompt_file)


def get_fusion_measurement_name() -> str:
    return os.getenv("FUSION_MEASUREMENT", "fusion_result")


def get_vllm_health_url() -> str:
    return f"http://{os.getenv('VLLM_HOST', 'vllm-server')}:{os.getenv('VLLM_PORT', '8000')}/docs"


def get_influx_client() -> InfluxDBClient:
    """Connect to the same InfluxDB database used by the former workbench."""
    return InfluxDBClient(
        host=os.getenv("INFLUX_HOST", "localhost"),
        port=int(os.getenv("INFLUX_PORT", "8086")),
        username=os.getenv("INFLUX_USER", "admin"),
        password=os.getenv("INFLUX_PASSWORD", "admin"),
        database=os.getenv("INFLUX_DB", "datain"),
        timeout=10,
    )


def fetch_rows(
    client: InfluxDBClient, page: int, page_size: int
) -> tuple[list[dict[str, Any]], bool]:
    """Read one page of fused results and determine whether another exists."""
    offset = (page - 1) * page_size
    no_result_re = r"/^(No_Weld|No Weld|No_Label|No Label|No label)$/"

    # page and page_size have been converted to integers and bounded by the caller.
    query = (
        "SELECT time, timeseries_classification, vision_classification, fused_decision "
        f"FROM {get_fusion_measurement_name()} "
        f"WHERE vision_classification !~ {no_result_re} "
        f"AND timeseries_classification !~ {no_result_re} "
        f"ORDER BY time DESC LIMIT {page_size + 1} OFFSET {offset}"
    )  # nosec B608
    points = list(client.query(query).get_points())
    return points[:page_size], len(points) > page_size


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Render the workbench alongside the other UI pages."""
    return templates.TemplateResponse(
        request=request,
        name="insights.html",
        context={
            "agentic_ui_enabled": os.getenv("AGENTIC_UI_ENABLED", "true").lower() == "true",
            "agentic_ui_root": os.getenv("REST_API_ROOT_PATH", "").rstrip("/"),
        },
    )


@router.get("/api/measurements")
def api_measurements() -> dict[str, list[str]]:
    """Keep the workbench's configured measurement selector API."""
    return {"measurements": [get_fusion_measurement_name()]}


@router.get("/api/data")
def api_data(page: int = 1, page_size: int = 10) -> Any:
    """Return a paginated set of fusion rows for the workbench table."""
    measurement = get_fusion_measurement_name()
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)

    try:
        client = get_influx_client()
        try:
            rows, has_more = fetch_rows(client, page, page_size)
        finally:
            client.close()
        return {
            "measurement": measurement,
            "page": page,
            "page_size": page_size,
            "has_more": has_more,
            "rows": rows,
        }
    except Exception:  # noqa: BLE001
        log.exception("Failed to fetch fusion rows for measurement=%s", measurement)
        return JSONResponse({"error": "Unable to load data", "rows": []}, status_code=500)


@router.get("/api/vllm/health")
def api_vllm_health() -> JSONResponse:
    """Report vLLM readiness independently of the UI container health check."""
    try:
        with urlopen(get_vllm_health_url(), timeout=5) as response:  # nosec B310
            accessible = 200 <= response.getcode() < 400
        return JSONResponse({"accessible": accessible}, status_code=200 if accessible else 503)
    except Exception:  # noqa: BLE001
        log.info("vLLM is not ready at %s", get_vllm_health_url(), exc_info=True)
        return JSONResponse({"accessible": False}, status_code=503)


@router.post("/api/explain")
def api_explain(payload: ExplainRequest) -> Any:
    """Combine selected vision/sensor data with the vLLM weld-quality prompt."""
    selected_times = payload.selected_times

    ts_data: list[str] = []
    resolved_images: list[dict[str, Any]] = []
    message: dict[str, Any] = {"role": "user", "content": []}

    try:
        client = get_influx_client()
        try:
            for time_str in selected_times:
                # The timestamp is ISO-8601 validated before interpolation.
                query = f"SELECT * FROM {get_fusion_measurement_name()} WHERE time = '{time_str}'"  # nosec B608
                points = list(client.query(query).get_points())
                if not points:
                    log.warning("No fusion result for time=%s", time_str)
                    continue

                row = points[0]
                vision_timestamp = row.get("vision_timestamp")
                if not vision_timestamp:
                    log.warning("No vision timestamp for time=%s", time_str)
                    continue

                vision_query = (
                    'SELECT * FROM "vision-weld-classification-results" '
                    f"WHERE search_time = '{vision_timestamp}'"
                )  # nosec B608
                vision_points = list(client.query(vision_query).get_points())

                image_data_url = None
                if vision_points:
                    frame_id = vision_points[0].get("frame_id")
                    img_handle = vision_points[0].get("img_handle")
                    image_url = build_image_url(str(img_handle)) if img_handle else None
                    image_data_url = build_image_data_url(image_url) if image_url else None
                    bucket = os.getenv("BUCKET_NAME", "dlstreamer-pipeline-results/weld-defect-classification")
                    resolved_images.append(
                        {
                            "selected_time": time_str,
                            "frame_id": frame_id,
                            "img_handle": img_handle,
                            "image_url": image_url,
                            "image_load_url": f"/image-store/buckets/{bucket}/{img_handle}.jpg" if img_handle else None,
                        }
                    )

                if image_data_url is None:
                    log.warning("Weld image unavailable for time=%s", time_str)
                    return JSONResponse({"error": "Weld image unavailable for selected time"}, status_code=502)

                sensor_query = (
                    'SELECT * FROM "weld-sensor-anomaly-data" '
                    f"WHERE time = {row['timeseries_timestamp']}"
                )  # nosec B608
                sensor_points = list(client.query(sensor_query).get_points())
                if not sensor_points:
                    log.warning("No sensor data for time=%s", time_str)
                    return JSONResponse({"error": "No sensor data found for selected time"}, status_code=404)
                sensor = sensor_points[0]

                sensor_text = f"""
                Sensor Data:
                    • Primary Weld Current: {sensor.get('Primary Weld Current', 'N/A')} A
                    • Secondary Weld Voltage: {sensor.get('Secondary Weld Voltage', 'N/A')} V
                    • Pressure: {sensor.get('Pressure', 'N/A')} bar
                    • CO2 Weld Flow: {sensor.get('CO2 Weld Flow', 'N/A')} L/min
                    • Feed: {sensor.get('Feed', 'N/A')} mm/min
                    • Wire Consumed: {sensor.get('Wire Consumed', 'N/A')} mm
                    """
                ts_data.append(sensor_text)
                message["content"].append(
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                )
                message["content"].append(
                    {
                        "type": "text",
                        "text": """Given this weld image and the sensor telemetry, produce a structured
                weld quality report covering defect classification, root cause, and remediation steps.
                """ + sensor_text,
                    }
                )
        finally:
            client.close()
    except Exception:  # noqa: BLE001
        log.exception("Unable to process explain request")
        return JSONResponse({"error": "Unable to process explain request"}, status_code=500)
    if not message["content"]:
         return JSONResponse({"error": "No explainable data found"}, status_code=404)
    try:
        response = vllm_client.chat.completions.create(
            model=os.getenv("VLLM_ADAPTER_NAME", "qwen3.5-2b-adapter"),
            messages=[get_query_prompt(), message],
            max_tokens=int(os.getenv("VLLM_CLIENT_TOKEN", "2048")),
            temperature=float(os.getenv("VLLM_CLIENT_TEMPERATURE", "1.5")),
            extra_body={"min_p": float(os.getenv("VLLM_CLIENT_MIN_P", "0.1"))},
        )
        vllm_output = response.choices[0].message.content or "" if response.choices else ""
    except Exception:  # noqa: BLE001
        log.exception("vLLM explanation failed")
        return JSONResponse({"error": "Unable to generate explanation"}, status_code=500)

    return {
        "title": "AI Assistant Output",
        "markdown": vllm_output,
        "selected_times": selected_times,
        "resolved_images": resolved_images,
        "ts_data": ts_data,
    }