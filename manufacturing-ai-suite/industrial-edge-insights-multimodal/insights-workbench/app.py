import os
import time
from typing import Any

from flask import Flask, jsonify, render_template, request
from influxdb import InfluxDBClient

app = Flask(__name__)


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
    measurement: str,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], bool]:
    offset = (page - 1) * page_size

    # Request one extra record so we can determine if there is a next page.
    query = (
        f'SELECT * FROM "{measurement}" '
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
        rows, has_more = fetch_rows(client, measurement, page, page_size)

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
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
