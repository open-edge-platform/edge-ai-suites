# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import math
import json
import pickle
import time
from datetime import timedelta
from urllib.request import Request, urlopen

import numpy as np
from sklearnex import config_context, patch_sklearn

patch_sklearn()

MODEL_CACHE = {}
INPUT_TABLE = "wind-turbine-data"
OUTPUT_TABLE = "wind-turbine-anomaly-data"


def _load_model(args):
    model_path = args.get("model_path") if args else None
    if not model_path:
        raise ValueError("model_path is required in trigger arguments")
    if model_path not in MODEL_CACHE:
        with open(model_path, "rb") as model_file:
            MODEL_CACHE[model_path] = pickle.load(model_file)
    return MODEL_CACHE[model_path]


def _should_predict(wind_speed, actual_power):
    if not math.isfinite(float(wind_speed)) or not math.isfinite(float(actual_power)):
        return False
    if wind_speed <= 3 or (wind_speed > 3 and actual_power < 50) or wind_speed > 14:
        return False
    return True


def _anomaly_status(predicted_power, actual_power):
    if predicted_power <= 0:
        return 0.0
    error = np.float32((predicted_power - actual_power) / predicted_power)
    if error <= np.float32(0.1):
        return 0.0
    if error < np.float32(0.3):
        return 0.3
    if error < np.float32(0.6):
        return 0.6
    return 1.0


def _publish_alerts(influxdb3_local, args, messages):
    if not messages or not args:
        return
    for message in messages:
        influxdb3_local.info("ALERT alerts/wind_turbine", message)
    if args.get("mqtt_host"):
        client = None
        try:
            import paho.mqtt.client as mqtt

            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.connect(args["mqtt_host"], int(args.get("mqtt_port", "1883")), keepalive=10)
            client.loop_start()
            pending = [
                client.publish(
                    args.get("mqtt_topic", "alerts/wind_turbine"),
                    message,
                    qos=int(args.get("mqtt_qos", "1")),
                )
                for message in messages
            ]
            for publish_result in pending:
                publish_result.wait_for_publish(timeout=5)
        except Exception as error:
            influxdb3_local.warn("Unable to publish Wind Turbine MQTT alert:", error)
        finally:
            if client is not None:
                client.loop_stop()
                client.disconnect()
    if args.get("opcua_url"):
        for message in messages:
            try:
                request = Request(
                    args["opcua_url"],
                    data=json.dumps({"alert": message}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    if response.status >= 400:
                        raise RuntimeError(f"OPC UA alert API returned HTTP {response.status}")
                influxdb3_local.info("ALERT sent to OPC UA server:", message)
            except Exception as error:
                influxdb3_local.warn("Unable to forward Wind Turbine OPC UA alert:", error)


def _process_rows(influxdb3_local, rows, args):
    if not rows:
        return

    eligible = []
    point_info = []
    for row in rows:
        wind_speed = row.get("wind_speed")
        actual_power = row.get("grid_active_power")
        analytic = wind_speed is not None and actual_power is not None
        should_predict = analytic and _should_predict(wind_speed, actual_power)
        point_info.append((row, analytic, should_predict))
        if should_predict:
            eligible.append([np.float32(wind_speed)])

    predictions = []
    inference_ns_per_point = 0
    if eligible:
        inference_start_ns = time.time_ns()
        with config_context(
            target_offload=(args or {}).get("device", "auto"),
            allow_fallback_to_host=True,
        ):
            predictions = _load_model(args).predict(np.asarray(eligible, dtype=np.float32))
        inference_ns_per_point = (time.time_ns() - inference_start_ns) / len(eligible)

    prediction_index = 0
    alert_messages = []
    for row, analytic, should_predict in point_info:
        point_start_ns = time.time_ns()
        anomaly_status = 0.0
        predicted_power = None
        if should_predict:
            predicted_power = np.float32(predictions[prediction_index])
            prediction_index += 1
            anomaly_status = _anomaly_status(
                predicted_power,
                np.float32(row["grid_active_power"]),
            )

        result = LineBuilder(OUTPUT_TABLE)
        if row.get("source") is not None:
            result.tag("source", row["source"])
        for field in ("wind_speed", "grid_active_power"):
            if row.get(field) is not None:
                result.float64_field(field, float(row[field]))
        result.bool_field("analytic", analytic)
        result.float64_field("anomaly_status", anomaly_status)
        now_ns = time.time_ns()
        result.float64_field(
            "processing_time",
            float(now_ns - point_start_ns + inference_ns_per_point),
        )
        if row.get("time") is not None:
            result.float64_field("end_end_time", float(now_ns - int(row["time"])))
            result.time_ns(int(row["time"]))
        if predicted_power is not None:
            result.float64_field("poc_predicted_power", float(predicted_power))
        influxdb3_local.write(result)
        if anomaly_status > 0:
            alert_messages.append(
                f"Anomaly detected for wind speed: {row.get('wind_speed')} "
                f"Grid Active Power: {row.get('grid_active_power')} "
                f"Anomaly Status: {anomaly_status}"
            )

    _publish_alerts(influxdb3_local, args, alert_messages)


def process_writes(influxdb3_local, table_batches, args=None):
    for table_batch in table_batches:
        if table_batch["table_name"] == INPUT_TABLE:
            _process_rows(influxdb3_local, table_batch["rows"], args)


def process_scheduled_call(influxdb3_local, schedule_time, args=None):
    window_start = (schedule_time - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
    window_end = schedule_time.strftime("%Y-%m-%d %H:%M:%S")
    rows = influxdb3_local.query(
        f'SELECT * FROM "{INPUT_TABLE}" '
        f"WHERE time >= '{window_start}'::TIMESTAMP "
        f"AND time < '{window_end}'::TIMESTAMP ORDER BY time"
    )
    influxdb3_local.info("Processing Wind Turbine window", window_start, window_end, "rows", len(rows))
    _process_rows(influxdb3_local, rows, args)
