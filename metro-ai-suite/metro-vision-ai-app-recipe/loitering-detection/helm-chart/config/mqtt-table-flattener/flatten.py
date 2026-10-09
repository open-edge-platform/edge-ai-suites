#!/usr/bin/env python3
"""
Subscribes to the raw per-frame DLSPS metadata topic (object_tracking/<id>,
published verbatim by gvametaconvert - untouched) and republishes a lightweight,
one-row-per-object summary to loiter_status/<id> so Grafana's MQTT table panel
can render it directly (grafana-mqtt-datasource maps one MQTT message to one
table row, so a nested "objects" array in a single message can't become rows).

Publish cadence is decoupled from the DLSPS frame rate (~30fps) via a periodic
timer; otherwise every still-dwelling object would republish every frame and
flood the table with near-duplicate rows. Zone/dwell-time are never computed
here - that is done entirely upstream by gvaanalytics; this script only
reshapes already-computed metadata for display.
"""
import json
import os
import threading
import time

import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
# Matches the topic prefixes sample_start.sh/benchmark_app_payload.json launch pipelines with;
# override via env instead of editing code if those are ever changed.
SOURCE_TOPIC_PREFIX = os.environ.get("SOURCE_TOPIC_PREFIX", "object_tracking")
DEST_TOPIC_PREFIX = os.environ.get("DEST_TOPIC_PREFIX", "loiter_status")
SOURCE_TOPIC = f"{SOURCE_TOPIC_PREFIX}/+"
PUBLISH_INTERVAL_SEC = float(os.environ.get("PUBLISH_INTERVAL_SEC", "1.0"))
# A pipeline publishes frames continuously (~30fps); once a stream has been
# silent longer than this, treat it as stopped so its rows stop being
# rebroadcast forever and the table actually empties out.
STALE_AFTER_SEC = float(os.environ.get("STALE_AFTER_SEC", "3.0"))

_lock = threading.Lock()
_latest_rows = {}  # stream_id -> list of row dicts, from the most recent frame
_last_seen = {}  # stream_id -> time.monotonic() of the last received frame


def on_connect(client, userdata, flags, rc):
    client.subscribe(SOURCE_TOPIC)


def on_message(client, userdata, msg):
    stream_id = msg.topic.rsplit("/", 1)[-1]
    try:
        payload = json.loads(msg.payload)
    except (ValueError, TypeError):
        return

    rows = []
    for obj in payload.get("metadata", {}).get("objects", []):
        dwell_times = obj.get("dwell_times")
        if not dwell_times:
            continue
        dwell = dwell_times[0]
        rows.append({
            "Stream": stream_id,
            "Track ID": obj.get("id"),
            "Type": obj.get("roi_type"),
            "Zone": dwell.get("zone_id"),
            "Dwell Time (s)": round(dwell.get("dwell_time_sec", 0), 1),
        })

    with _lock:
        _latest_rows[stream_id] = rows
        _last_seen[stream_id] = time.monotonic()


def publish_loop(client):
    while True:
        time.sleep(PUBLISH_INTERVAL_SEC)
        now = time.monotonic()
        with _lock:
            snapshot = {
                stream_id: list(rows)
                for stream_id, rows in _latest_rows.items()
                if now - _last_seen.get(stream_id, 0) <= STALE_AFTER_SEC
            }
        for stream_id, rows in snapshot.items():
            for row in rows:
                client.publish(f"{DEST_TOPIC_PREFIX}/{stream_id}", json.dumps(row), qos=0)


def main():
    # paho-mqtt 1.x API (matches the version already bundled in the
    # dlstreamer-pipeline-server image this script runs in - no pip install needed)
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    threading.Thread(target=publish_loop, args=(client,), daemon=True).start()
    client.loop_forever()


if __name__ == "__main__":
    main()
