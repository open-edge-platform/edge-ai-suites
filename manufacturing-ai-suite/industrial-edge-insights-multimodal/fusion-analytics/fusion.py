#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""
Fusion Analytics Module

This module performs real-time data fusion between vision-based defect detection
and time-series anomaly detection for welding quality monitoring. It subscribes
to MQTT topics, matches messages based on timestamps, and fuses the results
using configurable logic (AND/OR operations).

Key Features:
- Real-time MQTT message processing
- Timestamp-based message matching with configurable tolerance
- Configurable fusion logic (AND/OR operations)
- Automatic buffer management for incoming messages
"""

import paho.mqtt.client as mqtt
from collections import deque
import os
import re
from typing import Dict, Optional, Any, Literal
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from influxdb import InfluxDBClient as Influx1Client
import logging
import uvicorn

from api import api_app, set_influx_client, API_PORT, FUSION_MEASUREMENT

# Configure logging

log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging_level = getattr(logging, log_level, logging.INFO)

# Configure logging
logging.basicConfig(
    level=logging_level,  # Set the log level to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log format
)
logger = logging.getLogger(__name__)

VISION_MEASUREMENT = "vision-weld-classification-results"

# ===================== CONFIGURATION =====================
# Buffers to store recent messages for timestamp matching
vision_buffer = deque(maxlen=100)     # Keep last 100 vision messages
ts_buffer = deque(maxlen=100)         # Keep last 100 time-series messages

# MQTT Broker Configuration
# Can be overridden via environment variables for containerized deployment
BROKER = os.getenv("MQTT_BROKER", "localhost")

# MQTT Topic Configuration
VISION_TOPIC = os.getenv("VISION_TOPIC", "vision_weld_defect_classification")
TS_TOPIC = os.getenv("TS_TOPIC", "ts_weld_anomaly_detection")
FUSION_TOPIC = os.getenv("FUSION_TOPIC", "fusion/anomaly_detection_results")

# Timestamp Matching Configuration
# 50 ms tolerance (in nanoseconds) for matching messages by timestamp
TOLERANCE_NS = int(float(os.getenv("TOLERANCE_NS", 50e6)))
# Fusion Logic Configuration
# "AND" means both systems must detect anomaly to raise alert
# "OR" means either system detecting anomaly raises alert
FUSION_MODE = str(os.getenv("FUSION_MODE", "OR"))  # "AND" or "OR"
logger.debug(type(FUSION_MODE), FUSION_MODE)

if FUSION_MODE not in ["AND", "OR"]:
    raise ValueError(f"FUSION_MODE must be 'AND' or 'OR' given value is {FUSION_MODE}")

# ── API Configuration ─────────────────────────────────────────────────────────
influx_client = None

_LABEL_NORMALIZATION = {
    "No_Weld": "No Weld",
    "Good_Weld": "Good Weld",
    "Porosity_with_Excessive_Penetration": "Porosity with Excessive Penetration",
    "Porosity_w_Excessive_Penetration": "Porosity with Excessive Penetration",
    "No Label": "No Label",
}


def normalize_label(label: str | None) -> str:
    """Normalize labels across vision/time-series naming variants."""
    if not label:
        return "No Label"
    return _LABEL_NORMALIZATION.get(str(label), str(label).replace("_", " "))


def combine_classifications(
    vision_label: str,
    timeseries_label: str,
    vision_confidence: float,
    timeseries_confidence: float,
) -> str:
    """Create one fused class label from vision and time-series labels.

    Returns a single conclusion: when labels differ, pick the one with higher confidence.
    """
    v = normalize_label(vision_label)
    t = normalize_label(timeseries_label)

    if v == "No Label" and t == "No Label":
        return "No Label"
    if v == "No Label":
        return t
    if t == "No Label":
        return v
    if v == t:
        return v
    return v if vision_confidence >= timeseries_confidence else t


def parse_ts_string_to_ns(ts_str: str) -> int:
    """Parse incoming timestamp strings into nanoseconds since epoch."""
    cleaned = ts_str.strip()
    # Common input shape from TS service: "YYYY-MM-DD HH:MM:SS.fffffffff +0000 UTC"
    cleaned = re.sub(r"\s+UTC$", "", cleaned, flags=re.IGNORECASE)
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"

    # Some payloads include a duplicated UTC offset, e.g. "+0000+00:00".
    cleaned = re.sub(r"([+-]\d{4})([+-]\d{2}:\d{2})$", r"\1", cleaned)

    # Accept either space or 'T' separator and optional timezone.
    match = re.match(
        r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(?:\s*([+-]\d{2}:?\d{2}))?$",
        cleaned,
    )
    if not match:
        raise ValueError(f"Unsupported timestamp format: {ts_str}")

    date_part, time_part, frac_part, tz_part = match.groups()
    frac_ns = int((frac_part or "").ljust(9, "0")[:9]) if frac_part else 0
    micros = frac_ns // 1_000
    ns_remainder = frac_ns % 1_000

    tz_token = tz_part or "+0000"
    tz_token = tz_token.replace(":", "")
    sign = 1 if tz_token[0] == "+" else -1
    tz_hours = int(tz_token[1:3])
    tz_mins = int(tz_token[3:5])
    offset = timezone(sign * timedelta(hours=tz_hours, minutes=tz_mins))

    dt = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M:%S")
    dt = dt.replace(microsecond=micros, tzinfo=offset).astimezone(timezone.utc)

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = dt - epoch
    seconds = delta.days * 86_400 + delta.seconds
    return seconds * 1_000_000_000 + dt.microsecond * 1_000 + ns_remainder


def ns_to_iso8601_utc(ts_ns: int) -> str:
    """Convert epoch nanoseconds to RFC3339 UTC string."""
    seconds, ns_remainder = divmod(int(ts_ns), 1_000_000_000)
    dt = datetime.fromtimestamp(seconds, tz=timezone.utc).replace(microsecond=ns_remainder // 1_000)
    return dt.isoformat().replace("+00:00", "Z")

# ===================== UTILITY FUNCTIONS =====================

def find_nearest(buf, ts, type):
    """
    Find message in buffer with nearest timestamp within tolerance.
    
    Args:
        buf: Buffer (deque) containing messages
        ts: Target timestamp in nanoseconds
        type: Message type ("vision" or "timeseries") for field access
        
    Returns:
        Index of nearest message if within tolerance, None otherwise
    """
    if not buf: 
        return None
    
    # Find the message with minimum timestamp difference
    if type == "vision":
        # Vision messages have timestamp in metadata.rtp.sender_ntp_unix_timestamp_ns
        nearest_index, nearest_item = min(enumerate(buf), key=lambda x: abs(x[1]["metadata"]["rtp"]["sender_ntp_unix_timestamp_ns"] - ts))
        diff = abs(nearest_item["metadata"]["rtp"]["sender_ntp_unix_timestamp_ns"] - ts)
    elif type == "timeseries":
        # Time-series messages have timestamp in time field
        nearest_index, nearest_item =  min(enumerate(buf), key=lambda x: abs(x[1]["time"] - ts))
        diff = abs(nearest_item["time"] - ts)

    # Check if the difference is within acceptable tolerance
    if diff > TOLERANCE_NS:
        return None
    return nearest_index

def diff_timestamps_ns(t1: int, t2: int) -> dict:
    """
    Compute difference between two nanosecond epoch timestamps.
    
    Args:
        t1: First timestamp in nanoseconds
        t2: Second timestamp in nanoseconds
        
    Returns:
        Dictionary with time differences in various units (ns, µs, ms, s)
    """
    diff_ns = abs(t1 - t2)  # Always positive difference
    delta = {
        "ns": diff_ns,
        "us": diff_ns / 1_000,
        "ms": diff_ns / 1_000_000,
        "s": diff_ns / 1_000_000_000,
    }

    # Debug output: show time difference in milliseconds
    logger.debug(f"Δ ms: {delta['ms']:.3f}")
    return delta

# ===================== MESSAGE QUEUES =====================
# Queues for incoming messages from different sources
# Each queue maintains a rolling buffer of recent messages for fusion
queues = {
    "ts": deque(maxlen=1000),      # Time-series anomaly detection messages
    "vision": deque(maxlen=1000)   # Vision-based defect detection messages
}

# ===================== MQTT CALLBACKS =====================

def on_connect(client, userdata, flags, rc):
    """
    Callback function called when MQTT client connects to broker.
    
    Args:
        client: MQTT client instance
        userdata: User-defined data
        flags: Response flags sent by broker
        rc: Connection result code (0 = success)
    """
    logger.info(f"Connected to MQTT broker with result code {rc}")
    # Subscribe to both vision and time-series topics
    client.subscribe([(VISION_TOPIC, 0), (TS_TOPIC, 0)])
    logger.info(f"Subscribed to topics: {VISION_TOPIC}, {TS_TOPIC}")

def on_message(client, userdata, msg):
    """
    Callback function called when a message is received on subscribed topics.
    
    Args:
        client: MQTT client instance
        userdata: User-defined data
        msg: MQTT message object containing topic and payload
    """
    try:
        payload = json.loads(msg.payload.decode())
        
        if msg.topic == TS_TOPIC:
            # Process time-series anomaly detection message
            ts_str = payload["time"]

            # Convert timestamp string to nanosecond epoch
            ts_epoch = parse_ts_string_to_ns(ts_str)
            payload["time"] = ts_epoch
            queues["ts"].append(payload)
            
            # Debug: uncomment to see incoming messages
            # logger.info(f"Received from TS: {payload}")
            
        elif msg.topic == VISION_TOPIC:
            # Process vision-based defect detection message
            if "metadata" not in payload or "rtp" not in payload["metadata"] or "sender_ntp_unix_timestamp_ns" not in payload["metadata"]["rtp"]:
                logger.warning(f"missing RTP timestamp metadata in vision message. Skipping timestamp-based fusion for frame_id: {payload['metadata'].get('frame_id', 'unknown')}")
                time = payload["metadata"]["time"]
            else:
                time = payload["metadata"]["rtp"]["sender_ntp_unix_timestamp_ns"]
                queues["vision"].append(payload)
            
            # Debug: uncomment to see incoming messages
            # logger.info(f"Received from Vision: {payload}")

            vision_confidence = 0
            vision_classification = "No Label"

            if "metadata" in payload and "objects" in payload["metadata"] and "classification/Model6" in payload["metadata"]["objects"][0]:
                if "label" in payload["metadata"]["objects"][0]["classification/Model6"]:
                    vision_classification = str(payload["metadata"]["objects"][0]["classification/Model6"]["label"])
                else:
                    vision_classification = "No Label"
                if "confidence" in payload["metadata"]["objects"][0]["classification/Model6"]:
                    vision_confidence = float(payload["metadata"]["objects"][0]["classification/Model6"]["confidence"])
                else:
                    vision_confidence = 0.0

            # Write vision weld classification results to InfluxDB
            json_body = [{
                "measurement": VISION_MEASUREMENT,
                "time": ns_to_iso8601_utc(int(time)),
                "tags": {
                    "search_time": int(time),
                    "label": vision_classification,
                    "confidence": vision_confidence
                },
                "fields": {
                    "frame_id": int(payload["metadata"]["frame_id"]),
                    "height": int(payload["metadata"]["height"]),
                    "width": int(payload["metadata"]["width"]),
                    "channels": int(payload["metadata"]["channels"]),
                    "caps": str(payload["metadata"]["caps"]),
                    "img_handle": str(payload["metadata"]["img_handle"]),
                    "objects": str(payload["metadata"]["objects"]),
                    "img_format": str(payload["metadata"]["img_format"]),
                    "pipeline": str(payload["metadata"]["pipeline"]),
                    "gva_meta": str(payload["metadata"]["gva_meta"]),
                    "resolution": str(payload["metadata"]["resolution"]),
                    "tags": str(payload["metadata"]["tags"]),
                    "metadata": str(payload["metadata"]),
                    "timestamp": int(payload["metadata"]["timestamp"])
                }
            }]
            try:
                influx_client.write_points(json_body)
            except Exception as e:
                logger.error(f"Failed to write vision data to InfluxDB: {e}")

    except Exception as e:
        logger.error(f"Error processing message on topic {msg.topic}: {e}")

# ===================== FUSION LOGIC =====================

def fuse_firstcome(mode: Literal["AND", "OR"] = "AND") -> Optional[Dict[str, Any]]:
    """
    Fuse one pair of messages based on first-come-first-serve strategy.
    
    This function implements a temporal fusion approach where:
    1. The oldest message from either queue is selected first
    2. A matching message is found in the other queue based on timestamp proximity
    3. Both messages are removed from queues after fusion
    4. Fusion decision is made using AND/OR logic
    
    Args:
        mode: Fusion mode - "AND" (both must detect anomaly) or "OR" (either detects anomaly)
        
    Returns:
        Dictionary containing fusion results or None if no matching pair found
        Structure: {
            "from": source_entry,           # The first message processed
            "nearest": target_entry,        # The matching message found
            "mode": fusion_mode,            # AND/OR mode used
            "fused_decision": binary_result # Final fused decision (0/1)
        }
    """
    # Check if both queues have messages available
    if not queues["ts"] or not queues["vision"]:
        return None  # No pair available for fusion

    # Get the front (oldest) message from each queue
    front_ts = queues["ts"][0]
    front_vision = queues["vision"][0]

    # Determine which message came first based on timestamps
    if front_ts["time"] <= front_vision["metadata"]["rtp"]["sender_ntp_unix_timestamp_ns"]:
        # Time-series message is older, process it first
        source_queue = "ts"
        target_queue = "vision"
        source_entry = queues[source_queue].popleft()
        target_index = find_nearest(queues[target_queue], source_entry["time"], "vision")
    else:
        # Vision message is older, process it first
        source_queue = "vision"
        target_queue = "ts"
        source_entry = queues[source_queue].popleft()
        target_index = find_nearest(queues[target_queue], source_entry["metadata"]["rtp"]["sender_ntp_unix_timestamp_ns"], "timeseries")

    # Check if a matching message was found within tolerance
    if target_index is None:
        # No matching entry found, return partial result
        return {
            "from": source_entry, 
            "nearest": None, 
            "mode": mode, 
            "fused_decision": None, 
            "source_queue": source_queue,
            "target_queue": target_queue,
            "vision_anomaly": 0,
            "timeseries_anomaly": 0,
            "vision_classification": ""
        }

    logger.debug(f"Found nearest message at index: {target_index}")
    
    # Remove the matching message from the target queue
    target_entry = queues[target_queue][target_index]
    del queues[target_queue][target_index]

    vision_classification = "No Label"
    timeseries_classification = "No Label"

    data_dict = {}
    ts_time = None
    vision_rtp_time = None
    # Extract anomaly decisions from both messages
    if source_queue == "vision":
        # Vision message processed first
        vision_confidence = float(source_entry["metadata"]["objects"][0]["classification/Model6"].get("confidence", 0.0) or 0.0)
        vision_rtp_time = source_entry["metadata"].get("rtp", {}).get("sender_ntp_unix_timestamp_ns")
        ts_time = target_entry["time"]
        timeseries_anomaly = target_entry["anomaly_status"]
        timeseries_classification = target_entry.get("predicted_category", "No Label")
        timeseries_confidence = float(target_entry.get("confidence", 0) or 0)
        data_dict = source_entry
    else:
        # Time-series message processed first
        vision_confidence = float(target_entry["metadata"]["objects"][0]["classification/Model6"].get("confidence", 0.0) or 0.0)
        vision_rtp_time = target_entry["metadata"].get("rtp", {}).get("sender_ntp_unix_timestamp_ns")
        ts_time = source_entry["time"]
        timeseries_anomaly = source_entry["anomaly_status"]
        timeseries_classification = source_entry.get("predicted_category", "No Label")
        timeseries_confidence = float(source_entry.get("confidence", 0) or 0)
        data_dict = target_entry

    if "metadata" in data_dict and "label" in data_dict["metadata"]["objects"][0]["classification/Model6"]:
        vision_classification = str(data_dict["metadata"]["objects"][0]["classification/Model6"]["label"])

    fusion_confidence = (vision_confidence + timeseries_confidence) / 2.0
    fusion_classification = combine_classifications(
        vision_classification,
        timeseries_classification,
        vision_confidence,
        timeseries_confidence,
    )
    
    # Convert vision confidence to binary decision (threshold at 0.5)
    vision_anomaly = 1 if vision_confidence > 0.5 else 0
    
    if vision_classification == "No_Weld" or vision_classification == "Good_Weld":
        vision_anomaly = 0
    
    # Apply fusion logic based on selected mode
    if mode == "AND":
        # Both systems must detect anomaly
        fused_decision = vision_anomaly & timeseries_anomaly
    else:  # mode == "OR"
        # Either system detecting anomaly triggers alert
        fused_decision = vision_anomaly | timeseries_anomaly
    
    time_diff = diff_timestamps_ns(vision_rtp_time, ts_time) if vision_rtp_time is not None else None

    logger.info(f"Vision_Anomaly Type: {vision_classification}, Vision anomaly: {vision_anomaly}, TS anomaly: {timeseries_anomaly} fused decision: {fused_decision} time diff between RTP and ts: {time_diff['ms']:.3f} ms" if time_diff is not None else "N/A")

    
    return {
        "from": source_entry,
        "nearest": target_entry,
        "mode": mode,
        "fused_decision": fused_decision,
        "source_queue": source_queue,
        "target_queue": target_queue,
        "vision_anomaly": vision_anomaly,
        "timeseries_anomaly": timeseries_anomaly,
        "vision_classification": vision_classification,
        "timeseries_classification": timeseries_classification,
        "fusion_classification": fusion_classification,
        "vision_confidence": vision_confidence,
        "timeseries_confidence": timeseries_confidence,
        "fusion_confidence": fusion_confidence,
        "src_time_diff_ms": time_diff['ms'] if time_diff is not None else None
    }


# ===================== MAIN EXECUTION =====================

def main():
    global influx_client
    # Initialize MQTT client and configure callbacks
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to MQTT broker
    try:
        client.connect(BROKER, 1883, 60)
        logger.info(f"Fusion Analytics starting... Connected to {BROKER}")
        logger.info(f"Tolerance: {TOLERANCE_NS/1e6:.1f} ms")
        logger.info(f"Fusion mode: {FUSION_MODE}")
        INFLUX_HOST = os.getenv("INFLUXDB_HOST")
        INFLUX_PORT = int(os.getenv("INFLUXDB_PORT", "8086"))
        INFLUX_DB = os.getenv("INFLUXDB_DB", "datain")

        INFLUX_USER = os.getenv("INFLUXDB_USERNAME")
        INFLUX_PASS = os.getenv("INFLUXDB_PASSWORD")
        influx_client = Influx1Client(host=INFLUX_HOST, port=INFLUX_PORT, username=INFLUX_USER, password=INFLUX_PASS, database=INFLUX_DB)
        set_influx_client(influx_client)
    except Exception as e:
        logger.info(f"Failed to connect to MQTT broker: {e}")
        exit(1)

    # Start REST API in a background daemon thread
    api_thread = threading.Thread(
        target=lambda: uvicorn.run(api_app, host="0.0.0.0", port=API_PORT, log_level="warning"),
        daemon=True,
    )
    api_thread.start()
    logger.info("REST API listening on port %d", API_PORT)

    # Start MQTT message processing in background
    client.loop_start()

    # Main fusion processing loop
    try:
        while True:
            # Small delay to prevent excessive CPU usage
            time.sleep(1e-3)  # 1 millisecond
            
            # Attempt to fuse available messages
            result = fuse_firstcome(mode=FUSION_MODE)  # Can also try mode="OR"
            if result:
                logger.debug("=" * 60)
                logger.debug("FUSED RESULT:", result)
                logger.debug("=" * 60)
                # Write fused result to InfluxDB (InfluxDB v1.11.8)

                if result["fused_decision"] is not None:
                    ts = result["from"]["time"] if "time" in result["from"] else result["from"]["metadata"]["rtp"]["sender_ntp_unix_timestamp_ns"]
                    vision_time = result["from"]["metadata"]["rtp"]["sender_ntp_unix_timestamp_ns"] if "metadata" in result["from"] and "rtp" in result["from"]["metadata"] else None
                    if vision_time is None and "nearest" in result and result["nearest"] and "metadata" in result["nearest"] and "rtp" in result["nearest"]["metadata"]:
                        vision_time = result["nearest"]["metadata"]["rtp"]["sender_ntp_unix_timestamp_ns"]

                    timeseries_time = result["nearest"]["time"] if result["nearest"] and "time" in result["nearest"] else None
                    if timeseries_time is None and "from" in result and "time" in result["from"]:
                        timeseries_time = result["from"]["time"]
                    
                    json_body = [{
                        "measurement": FUSION_MEASUREMENT,
                        "time": ns_to_iso8601_utc(int(ts)),
                        "tags": {
                            "fusion_classification": str(result["fusion_classification"]) if result["fusion_classification"] is not None else None
                        },
                        "fields": {
                            "fusion_confidence": float(result["fusion_confidence"]) if result["fusion_confidence"] is not None else None,
                            "fused_decision": int(result["fused_decision"]),
                            "mode": str(result["mode"]),
                            "vision_classification": result["vision_classification"],
                            "timeseries_classification": result["timeseries_classification"],
                            "ts_anomaly": (
                                str(result["nearest"]["anomaly_status"])
                                if "anomaly_status" in result["nearest"]
                                else str(result["from"]["anomaly_status"])
                            ),
                            "vision_anomaly": int(result["vision_anomaly"]),
                            "timeseries_anomaly": int(result["timeseries_anomaly"]),
                            "vision_rtsp_ts_diff_ms": float(result["src_time_diff_ms"]) if result["src_time_diff_ms"] is not None else None,
                            "vision_timestamp": int(vision_time) if vision_time is not None else None,
                            "timeseries_timestamp": int(timeseries_time) if timeseries_time is not None else None,
                            "vision_confidence": float(result["vision_confidence"]) if result["vision_confidence"] is not None else None,
                            "timeseries_confidence": float(result["timeseries_confidence"]) if result["timeseries_confidence"] is not None else None

                        }
                    }]
                    influx_client.write_points(json_body)

                    json_body[0]["fields"]["time"] = json_body[0]["time"]
                    # Publish fused result to FUSION_TOPIC if needed
                    client.publish(FUSION_TOPIC, json.dumps(json_body[0]["fields"]))

    except KeyboardInterrupt:
        logger.info("\nShutting down Fusion Analytics...")
        influx_client.close()
        client.loop_stop()
        client.disconnect()
        logger.info("Disconnected from MQTT broker.")

if __name__ == "__main__":
    main()
