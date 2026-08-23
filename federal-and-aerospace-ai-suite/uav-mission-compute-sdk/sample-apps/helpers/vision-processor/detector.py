#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Vision Processor — YOLOv8n object detection via DL Streamer + OpenVINO.

Architecture:
  MQTT (raw frames) → In-memory queue → DL Streamer pipeline (gvadetect + gvawatermark)
  → appsink → Encode JPEG → MQTT (processed frames with bounding boxes)

Uses GStreamer DL Streamer for GPU-accelerated inference and overlay rendering.
"""
import json
import logging
import os
import time
import threading
from queue import Queue, Empty

import cv2
import numpy as np
import paho.mqtt.client as mqtt

import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
gi.require_version("GstAnalytics", "1.0")
from gi.repository import Gst, GstApp, GLib, GstAnalytics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("vision-processor")

# Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
UAV_ID = os.getenv("UAV_ID", "uav-1")
MODEL_XML = os.getenv("MODEL_XML", "/models/intel/yolo-v2-tiny-vehicle-detection-0001/FP16/yolo-v2-tiny-vehicle-detection-0001.xml")
MODEL_PROC = os.getenv("MODEL_PROC", "/opt/intel/dlstreamer/samples/model_proc/intel/yolo-v2-tiny-vehicle-detection-0001.json")
DEVICE = os.getenv("INFERENCE_DEVICE", "GPU")
CONF_THRESH = float(os.getenv("CONF_THRESH", "0.3"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1"))

TOPIC_IN = f"uav/{UAV_ID}/camera/frame"
TOPIC_OUT_FRAME = f"uav/{UAV_ID}/camera/processed"
TOPIC_OUT_DETECTIONS = f"uav/{UAV_ID}/detections"


class DLStreamerProcessor:
    """
    Native DL Streamer processor with YOLO v2 tiny vehicle detection (COCO-trained).

    Uses gvadetect + gvawatermark elements for GPU-accelerated inference and rendering.
    Pipeline: appsrc → videoconvert → videoscale → gvadetect → gvawatermark → appsink
    Model: yolo-v2-tiny-vehicle-detection-0001 (car, bus, truck detection)
    """

    def __init__(self, model_path: str, device: str, mqtt_pub_client):
        Gst.init(None)
        self.mqtt_client = mqtt_pub_client
        self.frame_count = 0
        self.detection_count = 0
        self.frame_width = None
        self.frame_height = None

        # YOLO v2 tiny vehicle detection model input size
        self.model_size = 416  # yolo-v2-tiny-vehicle-detection-0001 uses 416x416

        # Build native DL Streamer pipeline
        # gvadetect: YOLO v2 tiny vehicle detection (COCO-trained, better for aerial views)
        # gvawatermark: Hardware-accelerated bounding box rendering
        pipeline_str = (
            f"appsrc name=source format=time is-live=true block=true ! "
            f"videoconvert ! videoscale ! "
            f"video/x-raw,width={self.model_size},height={self.model_size} ! "
            f"gvadetect model={model_path} model-proc={MODEL_PROC} device={device} "
            f"batch-size={BATCH_SIZE} inference-interval=1 threshold={CONF_THRESH} ! queue ! "
            f"gvawatermark ! videoconvert ! "
            f"video/x-raw,format=BGR ! "
            f"appsink name=sink emit-signals=true max-buffers=2 drop=true"
        )

        log.info("Creating DL Streamer pipeline: %s", pipeline_str)
        self.pipeline = Gst.parse_launch(pipeline_str)

        # Get appsrc and appsink elements
        self.appsrc = self.pipeline.get_by_name("source")
        self.appsink = self.pipeline.get_by_name("sink")

        # Connect appsink callback to extract frames with rendered boxes
        self.appsink.connect("new-sample", self._on_new_sample, None)

        # Set pipeline to PLAYING state
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Failed to start DL Streamer pipeline")

        log.info("DL Streamer pipeline started: yolo-v2-tiny-vehicle-detection-0001 @ %s", device)

    def push_frame(self, jpeg_data: bytes):
        """Decode JPEG and push BGR frame into GStreamer pipeline."""
        try:
            # Decode JPEG to numpy array
            nparr = np.frombuffer(jpeg_data, dtype=np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return

            h, w = img.shape[:2]

            # Detect frame dimensions on first frame
            if self.frame_width is None:
                self.frame_width = w
                self.frame_height = h
                log.info("Detected camera resolution: %dx%d", w, h)

                # Set appsrc caps with detected dimensions
                caps = Gst.Caps.from_string(
                    f"video/x-raw,format=BGR,width={w},height={h},framerate=30/1"
                )
                self.appsrc.set_property("caps", caps)

            # Create GStreamer buffer from numpy array (original size)
            data = img.tobytes()
            buf = Gst.Buffer.new_allocate(None, len(data), None)
            buf.fill(0, data)
            buf.pts = self.frame_count * (Gst.SECOND // 30)  # 30 FPS timestamp
            buf.duration = Gst.SECOND // 30

            # Push buffer to appsrc
            ret = self.appsrc.emit("push-buffer", buf)
            if ret != Gst.FlowReturn.OK:
                log.warning("Failed to push buffer to pipeline: %s", ret)

        except Exception as e:
            log.error("Error pushing frame: %s", e)

    def _on_new_sample(self, sink, user_data):
        """
        Callback for processed frames from gvawatermark.

        Frames arrive with bounding boxes ALREADY DRAWN by gvawatermark element.
        Just pass them through to MQTT - no additional processing needed.
        """
        try:
            sample = sink.emit("pull-sample")
            if not sample:
                return Gst.FlowReturn.OK

            buffer = sample.get_buffer()
            caps = sample.get_caps()

            # Extract frame data (already has bounding boxes rendered by gvawatermark)
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if not success:
                return Gst.FlowReturn.OK

            # Parse caps
            structure = caps.get_structure(0)
            width = structure.get_value("width")
            height = structure.get_value("height")

            # Convert to numpy array (frame already has bounding boxes drawn)
            frame_data = np.ndarray(
                shape=(height, width, 3),
                dtype=np.uint8,
                buffer=map_info.data
            ).copy()

            buffer.unmap(map_info)

            # Encode as JPEG and publish to MQTT
            # Frame already has bounding boxes rendered by DL Streamer gvawatermark
            _, jpeg_buf = cv2.imencode(".jpg", frame_data, [cv2.IMWRITE_JPEG_QUALITY, 80])
            self.mqtt_client.publish(TOPIC_OUT_FRAME, jpeg_buf.tobytes(), qos=0)

            self.frame_count += 1

            if self.frame_count == 1:
                log.info("First frame processed - bounding boxes rendered by DL Streamer")
            elif self.frame_count % 100 == 0:
                log.info("Processed %d frames (boxes rendered by gvawatermark)", self.frame_count)

            return Gst.FlowReturn.OK

        except Exception as e:
            log.error("Error in appsink callback: %s", e)
            import traceback
            traceback.print_exc()
            return Gst.FlowReturn.ERROR

    def stop(self):
        """Stop the DL Streamer pipeline."""
        self.pipeline.set_state(Gst.State.NULL)
        log.info("DL Streamer pipeline stopped")


def main():
    # MQTT setup for receiving raw frames
    frame_queue = Queue(maxsize=5)

    def on_connect(client, userdata, flags, rc, properties):
        if rc == 0:
            log.info("MQTT connected, subscribing to %s", TOPIC_IN)
            client.subscribe(TOPIC_IN)
        else:
            log.error("MQTT connection failed: %d", rc)

    def on_message(client, userdata, msg):
        try:
            # Non-blocking put — drop oldest frame if queue is full
            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except Empty:
                    pass
            frame_queue.put_nowait(msg.payload)
        except Exception:
            pass  # Drop frame if queue operations fail

    mqtt_client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"vision-processor-{UAV_ID}",
    )
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    # Connect asynchronously - don't block
    try:
        mqtt_client.connect_async(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        log.info("MQTT connecting to %s:%d...", MQTT_BROKER, MQTT_PORT)
    except Exception as e:
        log.error("Failed to start MQTT client: %s", e)
        return

    log.info("Vision processor starting — %s → DL Streamer → %s", TOPIC_IN, TOPIC_OUT_FRAME)

    # Initialize DL Streamer processor
    try:
        processor = DLStreamerProcessor(MODEL_XML, DEVICE, mqtt_client)
    except Exception as e:
        log.error("Failed to initialize DL Streamer processor: %s", e)
        mqtt_client.loop_stop()
        return

    try:
        while True:
            try:
                # Get frame from queue (blocking with timeout)
                jpeg_data = frame_queue.get(timeout=1.0)
                processor.push_frame(jpeg_data)
            except Empty:
                continue

    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        processor.stop()
        mqtt_client.loop_stop()
        log.info("Vision processor stopped")


if __name__ == "__main__":
    main()
