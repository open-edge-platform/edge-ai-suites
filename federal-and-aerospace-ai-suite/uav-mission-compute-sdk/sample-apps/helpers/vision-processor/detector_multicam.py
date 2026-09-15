#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Multi-Camera Vision Processor — YOLOv8n object detection via DL Streamer + OpenVINO.

Subscribes to all camera frame topics for a uav, runs detection on each,
publishes both annotated frames and structured detection JSON per camera.
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
log = logging.getLogger("vision-multicam")

MQTT_BROKER = os.getenv("MQTT_BROKER_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
UAV_ID = os.getenv("UAV_ID", "uav-1")
MODEL_XML = os.getenv("MODEL_XML", "/models/intel/yolo-v2-tiny-vehicle-detection-0001/FP16/yolo-v2-tiny-vehicle-detection-0001.xml")
MODEL_PROC = os.getenv("MODEL_PROC", "/opt/intel/dlstreamer/samples/model_proc/intel/yolo-v2-tiny-vehicle-detection-0001.json")
DEVICE = os.getenv("INFERENCE_DEVICE", "GPU")
CONF_THRESH = float(os.getenv("CONF_THRESH", "0.6"))  # Higher threshold to reduce false positives
CAMERA_IDS = os.getenv("CAMERA_IDS", "nadir,forward,rear").split(",")

TOPIC_PATTERN = f"uav/{UAV_ID}/camera/+/frame"

_armed_state = {"armed": False}


class CameraProcessor:
    """Manages a per-camera DL Streamer pipeline."""

    def __init__(self, cam_id: str, mqtt_client: mqtt.Client):
        self.cam_id = cam_id
        self.mqtt_client = mqtt_client
        self.frame_count = 0
        self.detection_count = 0
        self.frame_width = None
        self.frame_height = None
        self.model_size = 416

        self.topic_out_frame = f"uav/{UAV_ID}/camera/{cam_id}/processed"
        self.topic_out_detections = f"uav/{UAV_ID}/camera/{cam_id}/detections"

        pipeline_str = (
            f"appsrc name=source format=time is-live=true block=true ! "
            f"videoconvert ! videoscale ! "
            f"video/x-raw,width={self.model_size},height={self.model_size} ! "
            f"gvadetect model={MODEL_XML} model-proc={MODEL_PROC} device={DEVICE} "
            f"batch-size=1 inference-interval=1 threshold={CONF_THRESH} ! queue ! "
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

        log.info("[%s] DL Streamer pipeline started", cam_id)

    def push_frame(self, jpeg_data: bytes):
        # Only process frames when uav is armed
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

    def _setup_detection_probe(self):
        """Attach a pad probe after gvadetect to capture detections before watermark."""
        # Find the queue element (between gvadetect and gvawatermark)
        queue = None
        it = self.pipeline.iterate_elements()
        while True:
            ret, elem = it.next()
            if ret != Gst.IteratorResult.OK:
                break
            if elem.get_factory() and elem.get_factory().get_name() == "queue":
                queue = elem
                break
        if queue:
            pad = queue.get_static_pad("src")
            if pad:
                pad.add_probe(Gst.PadProbeType.BUFFER, self._detection_probe_callback)
                log.info("[%s] Detection probe attached", self.cam_id)

    def _detection_probe_callback(self, pad, info):
        """Extract detection ROIs from buffer metadata."""
        buffer = info.get_buffer()
        if buffer is None:
            return Gst.PadProbeReturn.OK

        # Extract GstVideoRegionOfInterestMeta from buffer
        detections = []
        try:
            # Iterate through all metadata on the buffer
            meta = buffer.iterate_meta()
            if meta:
                while True:
                    try:
                        m = next(meta)
                        # Check if it's a video region of interest meta
                        api_type = m.get_info().get_type()
                        if "VideoRegionOfInterest" in api_type.name if hasattr(api_type, 'name') else "":
                            pass
                    except StopIteration:
                        break
                    except Exception:
                        break
        except Exception:
            pass

        # Alternative: check if gvawatermark rendered any boxes by comparing frames
        # For now, use the frame-differencing detection (watermark draws colored boxes)
        return Gst.PadProbeReturn.OK

    def _on_new_sample(self, sink, user_data):
        """Publish watermarked frame as JPEG and extract detections from rendered boxes."""
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

            # Detect bounding boxes from watermarked frame (gvawatermark draws green boxes)
            detections = self._detect_boxes_from_watermark(frame_data, width, height)

            _, jpeg_buf = cv2.imencode(".jpg", frame_data, [cv2.IMWRITE_JPEG_QUALITY, 80])
            self.mqtt_client.publish(self.topic_out_frame, jpeg_buf.tobytes(), qos=0)

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
        """
        Detect bounding boxes rendered by gvawatermark.
        gvawatermark draws blue rectangles — detect them via color thresholding in HSV.
        Filters out edge detections (likely uav wings) and very small detections.
        """
        detections = []
        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            # Blue range (gvawatermark default color is blue)
            lower_blue = np.array([100, 150, 150])
            upper_blue = np.array([130, 255, 255])
            mask = cv2.inRange(hsv, lower_blue, upper_blue)

            # Morphological close to connect box edges
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < 500:  # Increased minimum area
                    continue

                x, y, w, h = cv2.boundingRect(cnt)

                # Filter out detections too close to image edges (likely uav parts)
                edge_margin = 0.05  # 5% margin from edges
                x_center = (x + w/2) / width
                y_center = (y + h/2) / height

                if (x_center < edge_margin or x_center > (1 - edge_margin) or
                    y_center < edge_margin or y_center > (1 - edge_margin)):
                    continue

                aspect = w / max(h, 1)
                # More restrictive aspect ratio for vehicles
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

    frame_queues: dict[str, Queue] = {cam: Queue(maxsize=5) for cam in CAMERA_IDS}

    def on_connect(client, userdata, flags, rc, properties):
        if rc == 0:
            log.info("MQTT connected, subscribing to %s", TOPIC_PATTERN)
            client.subscribe(TOPIC_PATTERN)
            client.subscribe(f"uav/{UAV_ID}/telemetry/status")

    def on_message(client, userdata, msg):
        # Track armed state
        if "telemetry/status" in msg.topic:
            try:
                data = json.loads(msg.payload)
                was_armed = _armed_state["armed"]
                _armed_state["armed"] = data.get("armed", False)
                if _armed_state["armed"] != was_armed:
                    status = "ARMED - inference active" if _armed_state["armed"] else "DISARMED - inference paused"
                    log.info("UAV %s", status)
            except:
                pass
            return

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

    mqtt_client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"vision-multicam-{UAV_ID}",
    )
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect_async(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()

    log.info("=" * 60)
    log.info("MULTI-CAMERA VISION PROCESSOR")
    log.info("  UAV: %s | Cameras: %s", UAV_ID, CAMERA_IDS)
    log.info("  Model: %s @ %s", MODEL_XML, DEVICE)
    log.info("=" * 60)

    processors = {}
    for cam_id in CAMERA_IDS:
        try:
            processors[cam_id] = CameraProcessor(cam_id, mqtt_client)
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
