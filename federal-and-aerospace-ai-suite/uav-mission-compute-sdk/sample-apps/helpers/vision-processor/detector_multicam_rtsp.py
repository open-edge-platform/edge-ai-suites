#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Multi-Camera Vision Processor — YOLOv2-tiny via DL Streamer + OpenVINO (RTSP mode).

Subscribes to RTSP camera streams (or MQTT frames for legacy mode), runs detection,
publishes structured detection JSON and annotated frames to MQTT per camera.
"""
import json
import logging
import os
import time
import threading
from queue import Queue, Empty
from typing import Optional

import paho.mqtt.client as mqtt

import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
gi.require_version("GstAnalytics", "1.0")
from gi.repository import Gst, GstApp, GLib, GstAnalytics

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("vision-multicam")

# Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
UAV_ID = os.getenv("UAV_ID", "uav-1")
MODEL_XML = os.getenv("MODEL_XML", "/models/intel/yolo-v2-tiny-vehicle-detection-0001/FP16/yolo-v2-tiny-vehicle-detection-0001.xml")
MODEL_PROC = os.getenv("MODEL_PROC", "/opt/intel/dlstreamer/samples/model_proc/intel/yolo-v2-tiny-vehicle-detection-0001.json")
DEVICE = os.getenv("INFERENCE_DEVICE", "GPU")
CONF_THRESH = float(os.getenv("CONF_THRESH", "0.6"))
CAMERA_IDS = os.getenv("CAMERA_IDS", "nadir,forward,rear").split(",")

# RTSP Configuration
USE_RTSP = os.getenv("USE_RTSP", "false").lower() == "true"
RTSP_HOST = os.getenv("RTSP_HOST", "mediamtx")
RTSP_PORT = int(os.getenv("RTSP_PORT", "8554"))
RTSP_LATENCY = int(os.getenv("RTSP_LATENCY", "100"))  # ms
STREAM_FPS = int(os.getenv("STREAM_FPS", "30"))
INFERENCE_FPS = int(os.getenv("INFERENCE_FPS", "10"))
_INFER_INTERVAL = max(1, round(STREAM_FPS / INFERENCE_FPS)) if INFERENCE_FPS > 0 else 1

TOPIC_PATTERN = f"uav/{UAV_ID}/camera/+/frame"

_armed_state = {"armed": False}
_armed_changed = threading.Event()

RECONNECT_DELAY = 5  # seconds between RTSP reconnection attempts


class CameraProcessorRTSP:
    """Manages a per-camera DL Streamer pipeline consuming from RTSP.

    Lifecycle is tied to armed state:
      - Armed:    pipeline built and running
      - Disarmed: pipeline torn down (RTSP source would stall on dead stream)
    On re-arm the pipeline is rebuilt fresh, connecting to the newly-available stream.
    """

    def __init__(self, cam_id: str, mqtt_client: mqtt.Client):
        self.cam_id = cam_id
        self.mqtt_client = mqtt_client
        self.frame_count = 0
        self.detection_count = 0
        self.model_size = 416
        self._stop = threading.Event()

        self.rtsp_location = f"rtsp://{RTSP_HOST}:{RTSP_PORT}/{UAV_ID}/{cam_id}"
        self.topic_out_detections = f"uav/{UAV_ID}/camera/{cam_id}/detections"
        self.topic_out_processed = f"uav/{UAV_ID}/camera/{cam_id}/processed"

        self.pipeline = None
        self.appsink = None
        self._thread = threading.Thread(target=self._run_loop, daemon=True,
                                        name=f"rtsp-{cam_id}")
        self._thread.start()

    def _build_pipeline(self) -> bool:
        """Build and start the GStreamer pipeline. Returns True on success.

        Pipeline: RTSP in → decode → detect → watermark → appsink
          appsink extracts detection metadata (JSON → MQTT ``.../detections``)
          and re-encodes the annotated frame as JPEG (→ MQTT ``.../processed``).
          No annotated stream is pushed back to MediaMTX.
        """
        pipeline_str = (
            f"rtspsrc location={self.rtsp_location} latency={RTSP_LATENCY} protocols=tcp name=src ! "
            f"rtph264depay ! h264parse ! avdec_h264 ! "
            f"videoconvert ! videoscale ! "
            f"video/x-raw,width={self.model_size},height={self.model_size} ! "
            f"gvadetect model={MODEL_XML} model-proc={MODEL_PROC} device={DEVICE} "
            f"batch-size=1 inference-interval={_INFER_INTERVAL} threshold={CONF_THRESH} ! "
            f"queue ! gvawatermark ! videoconvert ! video/x-raw,format=BGR ! "
            f"appsink name=sink emit-signals=true max-buffers=2 drop=true"
        )
        try:
            self.pipeline = Gst.parse_launch(pipeline_str)
            self.appsink = self.pipeline.get_by_name("sink")
            self.appsink.connect("new-sample", self._on_new_sample, None)

            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                self.pipeline.set_state(Gst.State.NULL)
                self.pipeline = None
                return False

            log.info("[%s] RTSP DL Streamer pipeline started: %s  (inference every %d frames)",
                     self.cam_id, self.rtsp_location, _INFER_INTERVAL)
            return True
        except Exception as e:
            log.error("[%s] Failed to create RTSP pipeline: %s", self.cam_id, e)
            self.pipeline = None
            return False

    def _teardown_pipeline(self):
        """Stop and destroy the current pipeline."""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            self.appsink = None

    def _run_loop(self):
        """Main loop: manage pipeline lifecycle based on armed state."""
        while not self._stop.is_set():
            # Wait until armed
            while not self._stop.is_set() and not _armed_state["armed"]:
                _armed_changed.wait(timeout=1)
                _armed_changed.clear()

            if self._stop.is_set():
                break

            # Build pipeline
            if not self._build_pipeline():
                log.warning("[%s] RTSP not available, retrying in %ds", self.cam_id, RECONNECT_DELAY)
                self._stop.wait(RECONNECT_DELAY)
                continue

            # Run until disarmed or stream error
            bus = self.pipeline.get_bus()
            while not self._stop.is_set() and _armed_state["armed"]:
                msg = bus.timed_pop_filtered(
                    500 * Gst.MSECOND,
                    Gst.MessageType.ERROR | Gst.MessageType.EOS
                )
                if msg is None:
                    continue
                if msg.type == Gst.MessageType.ERROR:
                    err, debug = msg.parse_error()
                    log.warning("[%s] RTSP stream error: %s", self.cam_id, err)
                    break
                elif msg.type == Gst.MessageType.EOS:
                    log.info("[%s] RTSP stream ended", self.cam_id)
                    break

            # Teardown — either disarmed or stream error
            self._teardown_pipeline()

            # If stream error while still armed, wait before reconnecting
            if _armed_state["armed"] and not self._stop.is_set():
                log.info("[%s] Reconnecting to RTSP in %ds", self.cam_id, RECONNECT_DELAY)
                self._stop.wait(RECONNECT_DELAY)

    def _on_new_sample(self, sink, user_data):
        """Extract detections from watermarked frame and publish to MQTT."""
        if not _armed_state["armed"]:
            return Gst.FlowReturn.OK

        try:
            sample = sink.emit("pull-sample")
            if not sample:
                return Gst.FlowReturn.OK

            buffer = sample.get_buffer()
            caps = sample.get_caps()

            success, map_info = buffer.map(Gst.MapFlags.READ)
            if not success:
                return Gst.FlowReturn.OK

            structure = caps.get_structure(0)
            width = structure.get_value("width")
            height = structure.get_value("height")

            frame_data = np.ndarray(
                shape=(height, width, 3),
                dtype=np.uint8,
                buffer=map_info.data
            ).copy()

            buffer.unmap(map_info)

            detections = self._detect_boxes_from_watermark(frame_data, width, height)

            if detections:
                det_msg = {
                    "timestamp": time.time(),
                    "camera_id": self.cam_id,
                    "frame_id": self.frame_count,
                    "objects": [
                        {
                            "detection": {
                                "bounding_box": d["bbox"],
                                "label": d["label"],
                                "confidence": d["confidence"],
                            }
                        }
                        for d in detections
                    ],
                }
                self.mqtt_client.publish(
                    self.topic_out_detections, json.dumps(det_msg), qos=0
                )
                self.detection_count += len(detections)

            # Publish annotated frame (with bounding boxes) to MQTT
            _, jpeg_buf = cv2.imencode(".jpg", frame_data, [cv2.IMWRITE_JPEG_QUALITY, 80])
            self.mqtt_client.publish(
                self.topic_out_processed, jpeg_buf.tobytes(), qos=0
            )

            self.frame_count += 1
            if self.frame_count == 1:
                log.info("[%s] First frame processed from RTSP", self.cam_id)
            elif self.frame_count % 100 == 0:
                log.info("[%s] Processed %d frames, %d detections",
                         self.cam_id, self.frame_count, self.detection_count)

            return Gst.FlowReturn.OK
        except Exception as e:
            log.error("[%s] Appsink error: %s", self.cam_id, e)
            return Gst.FlowReturn.ERROR

    def _detect_boxes_from_watermark(self, frame: np.ndarray, width: int, height: int) -> list:
        """Detect bounding boxes rendered by gvawatermark via color thresholding."""
        detections = []
        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            lower_blue = np.array([100, 150, 150])
            upper_blue = np.array([130, 255, 255])
            mask = cv2.inRange(hsv, lower_blue, upper_blue)

            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < 500:
                    continue

                x, y, w, h = cv2.boundingRect(cnt)

                edge_margin = 0.05
                x_center = (x + w/2) / width
                y_center = (y + h/2) / height

                if (x_center < edge_margin or x_center > (1 - edge_margin) or
                    y_center < edge_margin or y_center > (1 - edge_margin)):
                    continue

                aspect = w / max(h, 1)
                if 0.3 < aspect < 3.5 and w > 30 and h > 30:
                    detections.append({
                        "label": "vehicle",
                        "confidence": 0.8,
                        "bbox": {
                            "x_min": round(x / width, 4),
                            "y_min": round(y / height, 4),
                            "x_max": round((x + w) / width, 4),
                            "y_max": round((y + h) / height, 4),
                        },
                    })
        except Exception:
            pass
        return detections

    def stop(self):
        self._stop.set()
        self._teardown_pipeline()


class CameraProcessorMQTT:
    """Manages a per-camera DL Streamer pipeline consuming from MQTT (legacy mode)."""

    def __init__(self, cam_id: str, mqtt_client: mqtt.Client):
        self.cam_id = cam_id
        self.mqtt_client = mqtt_client
        self.frame_count = 0
        self.detection_count = 0
        self.frame_width = None
        self.frame_height = None
        self.model_size = 416

        self.topic_out_detections = f"uav/{UAV_ID}/camera/{cam_id}/detections"
        self.topic_out_processed = f"uav/{UAV_ID}/camera/{cam_id}/processed"

        pipeline_str = (
            f"appsrc name=source format=time is-live=true block=true ! "
            f"videoconvert ! videoscale ! "
            f"video/x-raw,width={self.model_size},height={self.model_size} ! "
            f"gvadetect model={MODEL_XML} model-proc={MODEL_PROC} device={DEVICE} "
            f"batch-size=1 inference-interval={_INFER_INTERVAL} threshold={CONF_THRESH} ! queue ! "
            f"gvawatermark ! videoconvert ! "
            f"video/x-raw,format=BGR ! "
            f"appsink name=sink emit-signals=true max-buffers=2 drop=true"
        )

        self.pipeline = Gst.parse_launch(pipeline_str)
        self.appsrc = self.pipeline.get_by_name("source")
        self.appsink = self.pipeline.get_by_name("sink")
        self.appsink.connect("new-sample", self._on_new_sample, None)

        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError(f"Failed to start pipeline for {cam_id}")

        log.info("[%s] MQTT DL Streamer pipeline started", cam_id)

    def push_frame(self, jpeg_data: bytes):
        if not _armed_state["armed"]:
            return

        try:
            nparr = np.frombuffer(jpeg_data, dtype=np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return

            h, w = img.shape[:2]
            if self.frame_width is None:
                self.frame_width = w
                self.frame_height = h
                caps = Gst.Caps.from_string(
                    f"video/x-raw,format=BGR,width={w},height={h},framerate=30/1"
                )
                self.appsrc.set_property("caps", caps)

            data = img.tobytes()
            buf = Gst.Buffer.new_allocate(None, len(data), None)
            buf.fill(0, data)
            buf.pts = self.frame_count * (Gst.SECOND // 30)
            buf.duration = Gst.SECOND // 30
            self.appsrc.emit("push-buffer", buf)
        except Exception as e:
            log.error("[%s] Push frame error: %s", self.cam_id, e)

    def _on_new_sample(self, sink, user_data):
        """Publish watermarked frame as JPEG and extract detections."""
        try:
            sample = sink.emit("pull-sample")
            if not sample:
                return Gst.FlowReturn.OK

            buffer = sample.get_buffer()
            caps = sample.get_caps()

            success, map_info = buffer.map(Gst.MapFlags.READ)
            if not success:
                return Gst.FlowReturn.OK

            structure = caps.get_structure(0)
            width = structure.get_value("width")
            height = structure.get_value("height")

            frame_data = np.ndarray(
                shape=(height, width, 3),
                dtype=np.uint8,
                buffer=map_info.data
            ).copy()

            buffer.unmap(map_info)

            detections = self._detect_boxes_from_watermark(frame_data, width, height)

            if detections:
                det_msg = {
                    "timestamp": time.time(),
                    "camera_id": self.cam_id,
                    "frame_id": self.frame_count,
                    "objects": [
                        {
                            "detection": {
                                "bounding_box": d["bbox"],
                                "label": d["label"],
                                "confidence": d["confidence"],
                            }
                        }
                        for d in detections
                    ],
                }
                self.mqtt_client.publish(
                    self.topic_out_detections, json.dumps(det_msg), qos=0
                )
                self.detection_count += len(detections)

            # Publish annotated frame
            _, jpeg_buf = cv2.imencode(".jpg", frame_data, [cv2.IMWRITE_JPEG_QUALITY, 80])
            self.mqtt_client.publish(
                self.topic_out_processed, jpeg_buf.tobytes(), qos=0
            )

            self.frame_count += 1
            if self.frame_count == 1:
                log.info("[%s] First frame processed", self.cam_id)
            elif self.frame_count % 100 == 0:
                log.info("[%s] Processed %d frames, %d detections",
                         self.cam_id, self.frame_count, self.detection_count)

            return Gst.FlowReturn.OK
        except Exception as e:
            log.error("[%s] Appsink error: %s", self.cam_id, e)
            return Gst.FlowReturn.ERROR

    def _detect_boxes_from_watermark(self, frame: np.ndarray, width: int, height: int) -> list:
        """Same detection logic as RTSP mode."""
        detections = []
        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            lower_blue = np.array([100, 150, 150])
            upper_blue = np.array([130, 255, 255])
            mask = cv2.inRange(hsv, lower_blue, upper_blue)

            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < 500:
                    continue

                x, y, w, h = cv2.boundingRect(cnt)

                edge_margin = 0.05
                x_center = (x + w/2) / width
                y_center = (y + h/2) / height

                if (x_center < edge_margin or x_center > (1 - edge_margin) or
                    y_center < edge_margin or y_center > (1 - edge_margin)):
                    continue

                aspect = w / max(h, 1)
                if 0.3 < aspect < 3.5 and w > 30 and h > 30:
                    detections.append({
                        "label": "vehicle",
                        "confidence": 0.8,
                        "bbox": {
                            "x_min": round(x / width, 4),
                            "y_min": round(y / height, 4),
                            "x_max": round((x + w) / width, 4),
                            "y_max": round((y + h) / height, 4),
                        },
                    })
        except Exception:
            pass
        return detections

    def stop(self):
        self.pipeline.set_state(Gst.State.NULL)


def main():
    Gst.init(None)

    mqtt_client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"vision-multicam-{UAV_ID}",
    )

    def on_connect(client, userdata, flags, rc, properties):
        if rc == 0:
            log.info("MQTT connected, subscribing to telemetry/status")
            client.subscribe(f"uav/{UAV_ID}/telemetry/status")
            if not USE_RTSP:
                client.subscribe(TOPIC_PATTERN)
                log.info("Legacy MQTT mode: subscribed to %s", TOPIC_PATTERN)

    def on_message(client, userdata, msg):
        if "telemetry/status" in msg.topic:
            try:
                data = json.loads(msg.payload)
                was_armed = _armed_state["armed"]
                _armed_state["armed"] = data.get("armed", False)
                if _armed_state["armed"] != was_armed:
                    _armed_changed.set()
                    status = "ARMED - inference active" if _armed_state["armed"] else "DISARMED - inference paused"
                    log.info("UAV %s", status)
            except:
                pass
            return

        if not USE_RTSP:
            parts = msg.topic.split("/")
            if len(parts) >= 5 and parts[4] == "frame":
                cam_id = parts[3]
                if cam_id in frame_queues:
                    q = frame_queues[cam_id]
                    if q.full():
                        try:
                            q.get_nowait()
                        except Empty:
                            pass
                    try:
                        q.put_nowait(msg.payload)
                    except Exception:
                        pass

    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect_async(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()

    log.info("=" * 60)
    log.info("MULTI-CAMERA VISION PROCESSOR")
    log.info("  Mode:      %s", "RTSP" if USE_RTSP else "MQTT")
    log.info("  UAV:     %s | Cameras: %s", UAV_ID, CAMERA_IDS)
    log.info("  Model:     %s @ %s", MODEL_XML, DEVICE)
    if USE_RTSP:
        log.info("  RTSP:      %s:%d | Latency: %dms", RTSP_HOST, RTSP_PORT, RTSP_LATENCY)
        log.info("  Inference: %d FPS (every %d frames of %d FPS stream)",
                 INFERENCE_FPS if INFERENCE_FPS > 0 else STREAM_FPS, _INFER_INTERVAL, STREAM_FPS)
    log.info("=" * 60)

    processors = {}
    frame_queues = {}

    if USE_RTSP:
        for cam_id in CAMERA_IDS:
            try:
                processors[cam_id] = CameraProcessorRTSP(cam_id, mqtt_client)
            except Exception as e:
                log.error("Failed to create RTSP processor for %s: %s", cam_id, e)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("Shutting down...")
        finally:
            for p in processors.values():
                p.stop()
            mqtt_client.loop_stop()
    else:
        frame_queues = {cam: Queue(maxsize=5) for cam in CAMERA_IDS}

        for cam_id in CAMERA_IDS:
            try:
                processors[cam_id] = CameraProcessorMQTT(cam_id, mqtt_client)
            except Exception as e:
                log.error("Failed to create processor for %s: %s", cam_id, e)

        try:
            while True:
                for cam_id, q in frame_queues.items():
                    if cam_id not in processors:
                        continue
                    try:
                        jpeg_data = q.get(timeout=0.05)
                        processors[cam_id].push_frame(jpeg_data)
                    except Empty:
                        continue
        except KeyboardInterrupt:
            log.info("Shutting down...")
        finally:
            for p in processors.values():
                p.stop()
            mqtt_client.loop_stop()


if __name__ == "__main__":
    main()
