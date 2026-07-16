#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import datetime
import base64
import json
import logging
import mimetypes
import os
from typing import Any
from urllib.request import urlopen

from openai import OpenAI
from flask import Flask, jsonify, render_template, request
from influxdb import InfluxDBClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(process)d %(levelname)s %(name)s: %(message)s",
    force=True,
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

vllm_client = OpenAI(
    base_url= f"http://{os.getenv('VLLM_HOST', 'vllm-server')}:{os.getenv('VLLM_PORT', '8000')}/v1",
    api_key="EMPTY",
)

def get_seaweed_public_image_base_path() -> str:
    """Return the public SeaweedFS base path used to serve weld images."""
    return (
        f"{os.getenv('OBJECT_STORE_URL', 'http://seaweedfs-filer:8888')}/buckets/{os.getenv('BUCKET_NAME', 'dlstreamer-pipeline-results/weld-defect-classification')}"
    ).rstrip("/")
    
def build_image_url(img_handle: str) -> str:
    """Build a full image URL for a SeaweedFS image handle."""
    return f"{get_seaweed_public_image_base_path()}/{img_handle}.jpg"


def build_image_data_url(image_url: str) -> str | None:
    """Download an image and return it as a base64 data URL."""
    try:
        with urlopen(image_url, timeout=10) as response:
            image_bytes = response.read()
            header_mime = response.headers.get_content_type()

        mime_type = header_mime if header_mime and header_mime != "application/octet-stream" else None
        if not mime_type:
            guessed_mime, _ = mimetypes.guess_type(image_url)
            mime_type = guessed_mime or "image/jpeg"

        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{b64_image}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unable to build data URL for image=%s error=%s", image_url, exc)
        return None

def get_query_prompt() -> dict[str, Any]:
    """Return the system prompt that guides weld-quality analysis responses."""
    with open("/app/system_prompt.json", encoding="utf-8") as prompt_file:
        return json.load(prompt_file)


def get_fusion_measurement_name() -> str:
    """Return the InfluxDB measurement name used for fused analytics output."""
    return os.getenv("FUSION_MEASUREMENT", "fusion_result")


def get_vllm_health_url() -> str:
    """Return the vLLM health endpoint URL built from environment variables."""
    host = os.getenv("VLLM_HOST", "vllm-server")
    port = os.getenv("VLLM_PORT", "8000")
    return f"http://{host}:{port}/docs"


def get_influx_client() -> InfluxDBClient:
    """Create and return an InfluxDB client from environment configuration."""
    host = os.getenv("INFLUX_HOST", "localhost")
    port = int(os.getenv("INFLUX_PORT", "8086"))
    username = os.getenv("INFLUX_USER", "admin")
    password = os.getenv("INFLUX_PASSWORD", "admin")
    database = os.getenv("INFLUX_DB", "datain")

    return InfluxDBClient(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
        timeout=10,
    )


def list_measurements(client: InfluxDBClient) -> list[str]:
    """List available InfluxDB measurements."""
    result = client.query("SHOW MEASUREMENTS")
    measurements: list[str] = []

    for point in result.get_points():
        name = point.get("name")
        if name:
            measurements.append(str(name))

    return measurements


def fetch_rows(
    client: InfluxDBClient,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], bool]:
    """Fetch a page of fusion rows and indicate whether more rows are available."""
    offset = (page - 1) * page_size

    # Request one extra record so we can determine if there is a next page.
    query = (
        f'SELECT time, timeseries_classification, vision_classification, fused_decision FROM fusion_result '
        f"ORDER BY time DESC LIMIT {page_size + 1} OFFSET {offset}"
    )

    result = client.query(query)
    points = list(result.get_points())

    has_more = len(points) > page_size
    rows = points[:page_size]

    return rows, has_more


@app.route("/")
def index() -> str:
    """Render the main insights workbench page."""
    return render_template("index.html")


@app.route("/api/measurements", methods=["GET"])
def api_measurements() -> Any:
    """Return the configured fusion measurement for the frontend selector."""
    try:
        measurement = get_fusion_measurement_name()
        measurements = [measurement]
        return jsonify({"measurements": measurements})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc), "measurements": []}), 500


@app.route("/api/data", methods=["GET"])
def api_data() -> Any:
    """Return paginated fusion rows for the dashboard table."""
    measurement = get_fusion_measurement_name()
    page = max(int(request.args.get("page", 1)), 1)
    page_size = max(min(int(request.args.get("page_size", 10)), 200), 1)

    try:
        client = get_influx_client()
        rows, has_more = fetch_rows(client, page, page_size)

        return jsonify(
            {
                "measurement": measurement,
                "page": page,
                "page_size": page_size,
                "has_more": has_more,
                "rows": rows,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc), "rows": []}), 500


@app.route("/api/vllm/health", methods=["GET"])
def api_vllm_health() -> Any:
    """Check whether the vLLM server is accessible."""

    health_url = get_vllm_health_url()

    logger.info("Checking vLLM endpoint: %s", health_url)

    try:
        with urlopen(health_url, timeout=5) as response:
            status_code = response.getcode()

        accessible = 200 <= status_code < 400

        logger.info(
            "vLLM endpoint=%s status_code=%d accessible=%s",
            health_url,
            status_code,
            accessible,
        )

        return jsonify(
            {
                "accessible": accessible,
            }
        ), 200 if accessible else 503

    except Exception as exc:
        logger.error(
            "Unable to access vLLM endpoint=%s error=%s",
            health_url,
            exc,
        )

        return jsonify(
            {
                "accessible": False,
            }
        ), 503

@app.route("/api/explain", methods=["POST"])
def api_explain() -> Any:
    """Build multimodal context from selected timestamps and return an explanation payload."""
    payload = request.get_json(silent=True) or {}
    selected_times = payload.get("selected_times", [])
    logger.info("Explain request received with %d selected time(s)", len(selected_times))
    ts_data = []
    resolved_images: list[dict[str, Any]] = []
    message = {
        "role" :    "user",
        "content" : []
    }
    client = get_influx_client()
    for time_str in selected_times:
        try:
            datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            logger.info("Selected time=%s", time_str)
            query = f"SELECT * FROM fusion_result WHERE time = '{time_str}'"
            result = client.query(query)
            points = list(result.get_points())
            if len(points) == 0:
                logger.warning("No fusion_result row found for time=%s", time_str)
                continue

            row = points[0]
            vision_timestamp = row.get("vision_timestamp")
            if not vision_timestamp:
                logger.warning("No vision_timestamp found in fusion row for time=%s", time_str)
                continue

            query_vision = (
                f"SELECT * FROM \"vision-weld-classification-results\" "
                f"WHERE search_time = '{vision_timestamp}'"
            )
            logger.debug("Querying vision data with query: %s", query_vision)
            result_vision = client.query(query_vision)
            points_vision = list(result_vision.get_points())
            logger.info(
                "Matched %d row(s) for vision time=%s",
                len(points_vision),
                vision_timestamp,
            )

            img_handle = None
            image_url = None
            image_data_url = None

            if len(points_vision) > 0:
                frame_id = points_vision[0].get("frame_id")
                img_handle = points_vision[0].get("img_handle")
                image_url = build_image_url(str(img_handle)) if img_handle else None
                image_data_url = build_image_data_url(image_url) if image_url else None
                logger.debug(
                    "Retrieved frame_id=%s img_handle=%s image_url=%s",
                    frame_id,
                    img_handle,
                    image_url,
                )

                resolved_images.append(
                    {
                        "selected_time": time_str,
                        "frame_id": frame_id,
                        "img_handle": img_handle,
                        "image_url": image_url,
                        "image_load_url": f"/image-store/buckets/{os.getenv('BUCKET_NAME', 'dlstreamer-pipeline-results/weld-defect-classification')}/{img_handle}.jpg" if img_handle else None,
                    }
                )

            

            query_sensor = f"SELECT * FROM \"weld-sensor-anomaly-data\" WHERE time = {points[0]['timeseries_timestamp']}"
            logger.debug("Querying sensor data with query: %s", query_sensor)
            result_sensor = client.query(query_sensor)
            points_sensor = list(result_sensor.get_points())
            logger.debug("Matched %d row(s) for sensor time=%s", len(points_sensor), points[0]['timeseries_timestamp'])

            logger.info(f"Found {len(points_sensor)} sensor data point(s) for time={time_str}")

            vision_data = {
                "type": "image_url",
                "image_url": {
                    "url": image_data_url,
                },
            }

            sensors_data = {
                "type": "text",
                "text": f"""
                Given this weld image and the sensor telemetry, produce a structured
                weld quality report covering defect classification, root cause, and remediation steps.  
                Sensor Data:
                    • Primary Weld Current: {points_sensor[0].get('Primary Weld Current', 'N/A')} A
                    • Secondary Weld Voltage: {points_sensor[0].get('Secondary Weld Voltage', 'N/A')} V
                    • Pressure: {points_sensor[0].get('Pressure', 'N/A')} bar
                    • CO2 Weld Flow: {points_sensor[0].get('CO2 Weld Flow', 'N/A')} L/min
                    • Feed: {points_sensor[0].get('Feed', 'N/A')} mm/min
                    • Wire Consumed: {points_sensor[0].get('Wire Consumed', 'N/A')} mm
                    """,
            }

            ts_data.append(
                f"""
                Sensor Data:
                    • Primary Weld Current: {points_sensor[0].get('Primary Weld Current', 'N/A')} A
                    • Secondary Weld Voltage: {points_sensor[0].get('Secondary Weld Voltage', 'N/A')} V
                    • Pressure: {points_sensor[0].get('Pressure', 'N/A')} bar
                    • CO2 Weld Flow: {points_sensor[0].get('CO2 Weld Flow', 'N/A')} L/min
                    • Feed: {points_sensor[0].get('Feed', 'N/A')} mm/min
                    • Wire Consumed: {points_sensor[0].get('Wire Consumed', 'N/A')} mm
                    """
            )

            message["content"].append(vision_data)
            message["content"].append(sensors_data)
    
        except ValueError:
            return jsonify({"error": f"Invalid time format: {time_str}"}), 400
        except Exception as exc:  # noqa: BLE001
            logger.exception("Explain processing failed for time=%s", time_str)
            return jsonify({"error": str(exc)}), 500

    # Simulate a short model/API processing time for the UI spinner.
    

    final_prompt = [get_query_prompt(), message]
    logger.debug("Sending final prompt to vLLM: %s", final_prompt)
    response = vllm_client.chat.completions.create(
        model=os.getenv("VLLM_ADAPTER_NAME", "qwen3.5-2b-adapter"),
        messages=final_prompt,
        max_tokens=int(os.getenv("VLLM_CLIENT_TOKEN", "2048")),
        temperature=float(os.getenv("VLLM_CLIENT_TEMPERATURE", "1.5")),
        extra_body={
            "min_p": float(os.getenv("VLLM_CLIENT_MIN_P", "0.1")),
        },
    )

    vllm_output = ""
    if response.choices and len(response.choices) > 0:
        vllm_output = response.choices[0].message.content
        logger.info("vLLM response received with %d characters", len(vllm_output))
        logger.debug("vLLM output: %s", vllm_output)

    return jsonify(
        {
            "title": "AI Assistant Output",
            "markdown": vllm_output,
            "selected_times": selected_times,
            "resolved_images": resolved_images,
            "ts_data": ts_data,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
