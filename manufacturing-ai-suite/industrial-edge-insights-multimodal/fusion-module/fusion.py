import paho.mqtt.client as mqtt
import pandas as pd
from collections import deque
import os
from collections import deque
from typing import Dict, Optional, Any, Literal
import json
import time
# Buffers to store recent messages
vision_buffer = deque(maxlen=100)     # keep last 100 messages
ts_buffer = deque(maxlen=100)

BROKER = os.getenv("MQTT_BROKER", "localhost")
# BROKER = "localhost"

VISION_TOPIC = os.getenv("VISION_TOPIC", "vision_weld_defect_classification")
TS_TOPIC = os.getenv("TS_TOPIC", "ts_weld_defect_detection")
FUSION_TOPIC = os.getenv("FUSION_TOPIC", "fusion/anomaly")

# 50 ms tolerance (in ns)
TOLERANCE_NS = int(50e6)

def find_nearest(buf, ts, type):
    """Find message in buffer with nearest timestamp"""
    if not buf: return None
    if type == "vision":
        nearest_index, nearest_item = min(enumerate(buf), key=lambda x: abs(x[1]["metadata"]["time"] - ts))
        diff = abs(nearest_item["metadata"]["time"] - ts)
    elif type == "timeseries":
        nearest_index, nearest_item =  min(enumerate(buf), key=lambda x: abs(x[1]["time"] - ts))
        diff = abs(nearest_item["time"] - ts)

    if diff > TOLERANCE_NS:
        return None
    return nearest_index

def diff_timestamps_ns(t1: int, t2: int) -> dict:
    """
    Compute difference between two nanosecond epoch timestamps.
    Returns dict with ns, µs, ms, and s differences.
    """
    diff_ns = abs(t1 - t2)  # always positive
    delta = {
        "ns": diff_ns,
        "us": diff_ns / 1_000,
        "ms": diff_ns / 1_000_000,
        "s": diff_ns / 1_000_000_000,
    }

    # Example usage
    t1 = 1757405965894928834
    t2 = 1757405965841666048

    # delta = diff_timestamps_ns(t1, t2)
    # print(f"Δ ns: {delta['ns']}")
    # print(f"Δ µs: {delta['us']:.3f}")
    print(f"Δ ms: {delta['ms']:.3f}")
    # print(f"Δ s : {delta['s']:.6f}")

# Queues for incoming messages
queues = {
    "ts": deque(maxlen=1000),  # [{ts, anomaly}]
    "vision": deque(maxlen=1000)
}

# ----------------- MQTT CALLBACKS -----------------
def on_connect(client, userdata, flags, rc):
    print("Connected with result code", rc)
    client.subscribe([(VISION_TOPIC, 0), (TS_TOPIC, 0)])

def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    # Expect JSON: {"timestamp": 1696181200.23, "anomaly": 0/1}
    # entry = {"timestamp": ts, "anomaly": anomaly}

    if msg.topic == TS_TOPIC:
        ts_str = payload["time"]
        ts_str = ts_str.replace(" UTC", "")
        
        ts_epoch = pd.to_datetime(ts_str).value
        payload["time"] = ts_epoch
        queues["ts"].append(payload)
        
        # print(f"Received from ts: {payload}")
    elif msg.topic == VISION_TOPIC:
        queues["vision"].append(payload)
        # print(f"Received from module2: {payload}")

# # ----------------- HELPER FUNCTIONS -----------------
# def find_nearest(target_ts: float, queue: deque) -> Optional[int]:
#     """Return index of nearest timestamp entry in queue."""
#     if not queue:
#         return None
#     nearest_index, _ = min(
#         enumerate(queue),
#         key=lambda x: abs(x[1]["timestamp"] - target_ts)
#     )
#     return nearest_index

def fuse_firstcome(mode: Literal["AND", "OR"] = "AND") -> Optional[Dict[str, Any]]:
    """
    Fuse one pair of messages based on first-come-first-serve.
    Removes both entries after fusion.
    """
    if not queues["ts"] or not queues["vision"]:
        return None  # no pair available

    # Determine which queue has the oldest entry
    front1 = queues["ts"][0]
    front2 = queues["vision"][0]

    # print(f"Front ts: {front1}")
    # print(f"Front vision: {front2}")

    if front1["time"] <= front2["metadata"]["time"]:
        source_queue = "ts"
        target_queue = "vision"
        source_entry = queues[source_queue].popleft()
        target_index = find_nearest(queues[target_queue], source_entry["time"], "vision")
    else:
        source_queue = "vision"
        target_queue = "ts"
        source_entry = queues[source_queue].popleft()
        target_index = find_nearest(queues[target_queue], source_entry["metadata"]["time"], "timeseries")

    
    if target_index is None:
        # No matching entry, keep source removed
        return {"from": source_entry, "nearest": None, "fused": None}
    print(f"Found nearest index: {target_index}")
    target_entry = queues[target_queue][target_index]
    del queues[target_queue][target_index]

    if source_queue == "vision":
        vision_anomaly = source_entry["metadata"]["objects"][0]["classification_layer_name:output1"]["confidence"]
        
        timeseries_anomaly = target_entry["anomaly_status"]
    else:
        vision_anomaly = target_entry["metadata"]["objects"][0]["classification_layer_name:output1"]["confidence"]
        timeseries_anomaly = source_entry["anomaly_status"]
    vision_anomaly = 1 if vision_anomaly > 0.5 else 0
    print(vision_anomaly, timeseries_anomaly)
    # Fusion logic
    if mode == "AND":
        fused = vision_anomaly & timeseries_anomaly
    else:
        fused = vision_anomaly | timeseries_anomaly

    return {
        "from": source_entry,
        "nearest": target_entry,
        "mode": mode,
        "fused_decision": fused
    }


# MQTT setup
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, 1883, 60)

print("Fusion service running...")

client.loop_start()

try:
    while True:
        time.sleep(1e-3)
        # print("Running fusion check...")
        result = fuse_firstcome(mode="AND")  # can also try mode="OR"
        if result:
            print("FUSED RESULT:", result)
except KeyboardInterrupt:
    print("Exiting...")
    client.loop_stop()
    client.disconnect()