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
import pandas as pd
from collections import deque
import os
from collections import deque
from typing import Dict, Optional, Any, Literal
import json
import time
from influxdb import InfluxDBClient as Influx1Client
# ===================== CONFIGURATION =====================
# Buffers to store recent messages for timestamp matching
vision_buffer = deque(maxlen=100)     # Keep last 100 vision messages
ts_buffer = deque(maxlen=100)         # Keep last 100 time-series messages

# MQTT Broker Configuration
# Can be overridden via environment variables for containerized deployment
BROKER = os.getenv("MQTT_BROKER", "localhost")

# MQTT Topic Configuration
VISION_TOPIC = os.getenv("VISION_TOPIC", "vision_weld_defect_classification")
TS_TOPIC = os.getenv("TS_TOPIC", "ts_weld_defect_detection")
FUSION_TOPIC = os.getenv("FUSION_TOPIC", "fusion/anomaly")

# Timestamp Matching Configuration
# 50 ms tolerance (in nanoseconds) for matching messages by timestamp
TOLERANCE_NS = int(float(os.getenv("TOLERANCE_NS", 50e6)))
# Fusion Logic Configuration
# "AND" means both systems must detect anomaly to raise alert
# "OR" means either system detecting anomaly raises alert
FUSION_MODE = str(os.getenv("FUSION_MODE", "AND"))  # "AND" or "OR"
print(type(FUSION_MODE), FUSION_MODE)

if FUSION_MODE not in ["AND", "OR"]:
    raise ValueError(f"FUSION_MODE must be 'AND' or 'OR' given value is {FUSION_MODE}mhhvmhvmh")

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
        # Vision messages have timestamp in metadata.time
        nearest_index, nearest_item = min(enumerate(buf), key=lambda x: abs(x[1]["metadata"]["time"] - ts))
        diff = abs(nearest_item["metadata"]["time"] - ts)
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
    print(f"Δ ms: {delta['ms']:.3f}")
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
    print(f"Connected to MQTT broker with result code {rc}")
    # Subscribe to both vision and time-series topics
    client.subscribe([(VISION_TOPIC, 0), (TS_TOPIC, 0)])
    print(f"Subscribed to topics: {VISION_TOPIC}, {TS_TOPIC}")

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
            ts_str = ts_str.replace(" UTC", "")  # Clean timestamp format
            
            # Convert timestamp string to nanosecond epoch
            ts_epoch = pd.to_datetime(ts_str).value
            payload["time"] = ts_epoch
            queues["ts"].append(payload)
            
            # Debug: uncomment to see incoming messages
            # print(f"Received from TS: {payload}")
            
        elif msg.topic == VISION_TOPIC:
            # Process vision-based defect detection message
            queues["vision"].append(payload)
            
            # Debug: uncomment to see incoming messages
            # print(f"Received from Vision: {payload}")
            
    except Exception as e:
        print(f"Error processing message on topic {msg.topic}: {e}")

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
    if front_ts["time"] <= front_vision["metadata"]["time"]:
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
        target_index = find_nearest(queues[target_queue], source_entry["metadata"]["time"], "timeseries")

    # Check if a matching message was found within tolerance
    if target_index is None:
        # No matching entry found, return partial result
        return {"from": source_entry, "nearest": None, "mode": mode, "fused_decision": None}

    print(f"Found nearest message at index: {target_index}")
    
    # Remove the matching message from the target queue
    target_entry = queues[target_queue][target_index]
    del queues[target_queue][target_index]

    # Extract anomaly decisions from both messages
    if source_queue == "vision":
        # Vision message processed first
        vision_confidence = source_entry["metadata"]["objects"][0]["classification_layer_name:output1"]["confidence"]
        timeseries_anomaly = target_entry["anomaly_status"]
    else:
        # Time-series message processed first
        vision_confidence = target_entry["metadata"]["objects"][0]["classification_layer_name:output1"]["confidence"]
        timeseries_anomaly = source_entry["anomaly_status"]
    
    # Convert vision confidence to binary decision (threshold at 0.5)
    vision_anomaly = 1 if vision_confidence > 0.5 else 0
    
    print(f"Vision anomaly: {vision_anomaly}, TS anomaly: {timeseries_anomaly}")
    
    # Apply fusion logic based on selected mode
    if mode == "AND":
        # Both systems must detect anomaly
        fused_decision = vision_anomaly & timeseries_anomaly
    else:  # mode == "OR"
        # Either system detecting anomaly triggers alert
        fused_decision = vision_anomaly | timeseries_anomaly

    return {
        "from": source_entry,
        "nearest": target_entry,
        "mode": mode,
        "fused_decision": fused_decision
    }


# ===================== MAIN EXECUTION =====================

def main():
    # Initialize MQTT client and configure callbacks
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to MQTT broker
    try:
        client.connect(BROKER, 1883, 60)
        print(f"Fusion Analytics starting... Connected to {BROKER}")
        print(f"Tolerance: {TOLERANCE_NS/1e6:.1f} ms")
        print(f"Fusion mode: AND (both systems must agree)")
        INFLUX_HOST = os.getenv("INFLUXDB_HOST")
        INFLUX_PORT = int(os.getenv("INFLUXDB_PORT", "8086"))
        INFLUX_DB = os.getenv("INFLUXDB_DB", "datain")

        INFLUX_USER = os.getenv("INFLUXDB_USERNAME")
        INFLUX_PASS = os.getenv("INFLUXDB_PASSWORD")
        influx_client = Influx1Client(host=INFLUX_HOST, port=INFLUX_PORT, username=INFLUX_USER, password=INFLUX_PASS, database=INFLUX_DB)
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        exit(1)

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
                print("=" * 60)
                print("FUSED RESULT:", result)
                print("=" * 60)
                # Write fused result to InfluxDB (InfluxDB v1.11.8)

                ts = result["from"]["time"] if "time" in result["from"] else result["from"]["metadata"]["time"]
                json_body = [{
                    "measurement": "fusion_result",
                    "time": pd.to_datetime(ts, unit="ns").isoformat(),
                    "fields": {
                        "fused_decision": int(result["fused_decision"] if result["fused_decision"] is not None else -1),
                        "mode": str(result["mode"])
                    }
                }]
                influx_client.write_points(json_body)
                
                

                # TODO: Publish fused result to FUSION_TOPIC if needed
                # client.publish(FUSION_TOPIC, json.dumps(result))

    except KeyboardInterrupt:
        print("\nShutting down Fusion Analytics...")
        influx_client.close()
        client.loop_stop()
        client.disconnect()
        print("Disconnected from MQTT broker.")

if __name__ == "__main__":
    main()