import datetime
import logging
import os
import time
from typing import Any

from flask import Flask, jsonify, render_template, request
from influxdb import InfluxDBClient

app = Flask(__name__)
app.logger.setLevel(logging.INFO)


def get_fusion_measurement_name() -> str:
    return os.getenv("FUSION_MEASUREMENT", "fusion_result")


def get_influx_client() -> InfluxDBClient:
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
    return render_template("index.html")


@app.route("/api/measurements", methods=["GET"])
def api_measurements() -> Any:
    try:
        measurement = get_fusion_measurement_name()
        measurements = [measurement]
        return jsonify({"measurements": measurements})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc), "measurements": []}), 500


@app.route("/api/data", methods=["GET"])
def api_data() -> Any:
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


@app.route("/api/explain", methods=["POST"])
def api_explain() -> Any:
    payload = request.get_json(silent=True) or {}
    selected_times = payload.get("selected_times", [])
    app.logger.info("Explain request received with %d selected time(s)", len(selected_times))

    for time_str in selected_times:
        try:
            dt = datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            epoch_ns = int(dt.timestamp() * 1_000_000_000)
            app.logger.info("Selected time=%s epoch_ns=%d", time_str, epoch_ns)
            client = get_influx_client()
            query = f"SELECT * FROM fusion_result WHERE time = '{time_str}'"
            result = client.query(query)
            points = list(result.get_points())
            app.logger.info("Matched %d row(s) for time=%s row: %s", len(points), time_str, points[0])

#             vision-weld-classification-results
# weld-sensor-anomaly-data

            query_vision = f"SELECT * FROM \"vision-weld-classification-results\" WHERE search_time = '{points[0]['vision_timestamp']}'"
            app.logger.info("Querying vision data with query: %s", query_vision)
            result_vision = client.query(query_vision)
            points_vision = list(result_vision.get_points())
            app.logger.info("Matched %d row(s) for vision time=%s row: %s", len(points_vision), points[0]['vision_timestamp'], points_vision)

            if len(points_vision) > 0:
                frame_id = points_vision[0].get("frame_id")
                app.logger.info("Retrieved frame_id=%s for vision time=%s", frame_id, points[0]['vision_timestamp'])
            else:

            query_sensor = f"SELECT * FROM \"weld-sensor-anomaly-data\" WHERE time = {points[0]['timeseries_timestamp']}"
            app.logger.info("Querying sensor data with query: %s", query_sensor)
            result_sensor = client.query(query_sensor)
            points_sensor = list(result_sensor.get_points())
            app.logger.info("Matched %d row(s) for sensor time=%s row: %s", len(points_sensor), points[0]['timeseries_timestamp'], points_sensor)

            
        except ValueError:
            return jsonify({"error": f"Invalid time format: {time_str}"}), 400
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Explain processing failed for time=%s", time_str)
            return jsonify({"error": str(exc)}), 500

    # Simulate a short model/API processing time for the UI spinner.
    time.sleep(2)

    return jsonify(
        {
            "title": "AI Assistant Output",
            "section": "Root Cause Analysis",
            "bullets": [
                "WT-001 exhibited a sudden increase in vibration.",
                "Temperature rose 15% above baseline.",
                "Similar pattern observed in previous bearing failure.",
            ],
            "recommendation": "Inspect bearing assembly.",
            "selected_times": selected_times,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
