# =============================================================================
# Smart Tolling SceneScape Adapter - SIDE (Side Camera) [MAX TRACKING]
# =============================================================================
# Complete standalone adapter for Vehicle/Axle Detection.
# For use with toll-side pipeline.
#
# USAGE in config.json:
#   module=/home/pipeline-server/user_scripts/gvapython/sscape/sscape_adapter_side_max_tracking.py
#
# FEATURES:
#   - Vehicle type detection (van, truck, bus, car)
#   - Color classification
#   - Axle counting with ground contact filtering
#   - ROI-aware (works with gvaattachroi)
#   - MAX TRACKING: Remembers peak axle count + best side-view image
#     per vehicle across frames. Prevents partial-entry/exit from
#     under-counting axles or publishing half-vehicle images.
# =============================================================================

import base64
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime
from uuid import getnode as get_mac

import cv2
import ntplib
import paho.mqtt.client as mqtt
from pytz import timezone

from utils import publisher_utils as utils

# ==================== CONSTANTS ====================
ROOT_CA = os.environ.get('ROOT_CA', '/run/secrets/certs/scenescape-ca.pem')
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
TIMEZONE = "UTC"

DEBUG_MODE = os.environ.get('DEBUG_ADAPTER', 'false').lower() == 'true'

# Max tracking: how long (seconds) to keep a vehicle's memory after last seen
VEHICLE_MEMORY_TTL = 30

VEHICLE_TYPES = ('van', 'truck', 'bus', 'car', 'sedan', 'suv')
COLOR_LABELS = ('yellow', 'white', 'red', 'orange', 'grey', 'green', 'brown', 'blue', 'black')


# ==================== HELPER FUNCTIONS ====================

def getMACAddress():
    if 'MACADDR' in os.environ:
        return os.environ['MACADDR']
    a = get_mac()
    h = iter(hex(a)[2:].zfill(12))
    return ":".join(i + next(h) for i in h)


def computeObjBoundingBoxParams(pobj, fw, fh, x, y, w, h, xminnorm=None, yminnorm=None, xmaxnorm=None, ymaxnorm=None):
    try:
        xmax, xmin = int(xmaxnorm * fw), int(xminnorm * fw)
        ymax, ymin = int(ymaxnorm * fh), int(yminnorm * fh)
    except Exception:
        xmin, ymin, xmax, ymax = x, y, x + w, y + h

    comw, comh = (xmax - xmin) / 3, (ymax - ymin) / 4
    pobj.update({
        'center_of_mass': {'x': int(xmin + comw), 'y': int(ymin + comh), 'width': comw, 'height': comh},
        'bounding_box_px': {'x': x, 'y': y, 'width': w, 'height': h}
    })


def map_label_to_category(label):
    if not label:
        return 'unknown'
    lab = str(label).lower()
    if lab in ('vehicle', 'car', 'bus', 'truck', 'van', 'sedan', 'suv', 'motorcycle', 'bicycle'):
        return 'vehicle'
    if lab in ('person', 'pedestrian'):
        return 'pedestrian'
    if lab == 'axle':
        return 'axle'
    return 'unknown'


# ==================== GROUND/AXLE UTILITIES ====================

def get_ground_level(vehicle, axles):
    """Calculate ground Y coordinate from vehicle and overlapping axles."""
    vehicle_bottom = vehicle.get('y', 0) + vehicle.get('height', 0)
    vehicle_x = vehicle.get('x', 0)
    vehicle_right = vehicle_x + vehicle.get('width', 0)

    overlapping_axle_bottoms = []
    for axle in axles:
        axle_x = axle.get('x', 0)
        axle_right = axle_x + axle.get('width', 0)
        if axle_right > vehicle_x - 50 and axle_x < vehicle_right + 50:
            axle_bottom = axle.get('y', 0) + axle.get('height', 0)
            overlapping_axle_bottoms.append(axle_bottom)

    all_bottoms = [vehicle_bottom] + overlapping_axle_bottoms
    return max(all_bottoms)


def classify_axles_ground_contact(axles, ground_y, tolerance=30):
    """Classify each axle as touching or not touching ground."""
    results = []
    for axle in axles:
        axle_bottom = axle.get('y', 0) + axle.get('height', 0)
        touching = axle_bottom >= (ground_y - tolerance)
        results.append({
            'x': axle.get('x', 0),
            'y': axle.get('y', 0),
            'width': axle.get('width', 0),
            'height': axle.get('height', 0),
            'touching_ground': touching,
            'confidence': axle.get('confidence', 0.0)
        })
    return results


def is_axle_inside_vehicle(axle, vehicle, margin=50):
    """Check if axle's center is inside vehicle bbox."""
    axle_cx = axle.get('x', 0) + axle.get('width', 0) / 2
    axle_cy = axle.get('y', 0) + axle.get('height', 0) / 2
    vx = vehicle.get('x', 0) - margin
    vy = vehicle.get('y', 0) - margin
    vw = vehicle.get('width', 0) + 2 * margin
    vh = vehicle.get('height', 0) + 2 * margin
    return (vx <= axle_cx <= vx + vw and vy <= axle_cy <= vy + vh)


# ==================== WHEEL DEDUPLICATION (IoU-based) ====================

def compute_iou(box1, box2):
    """Compute Intersection over Union (IoU) between two bounding boxes.

    Each box should have keys: x, y, width, height.
    """
    x1_min = box1.get('x', 0)
    y1_min = box1.get('y', 0)
    x1_max = x1_min + box1.get('width', 0)
    y1_max = y1_min + box1.get('height', 0)

    x2_min = box2.get('x', 0)
    y2_min = box2.get('y', 0)
    x2_max = x2_min + box2.get('width', 0)
    y2_max = y2_min + box2.get('height', 0)

    inter_x_min = max(x1_min, x2_min)
    inter_y_min = max(y1_min, y2_min)
    inter_x_max = min(x1_max, x2_max)
    inter_y_max = min(y1_max, y2_max)

    inter_width = max(0, inter_x_max - inter_x_min)
    inter_height = max(0, inter_y_max - inter_y_min)
    inter_area = inter_width * inter_height

    area1 = box1.get('width', 0) * box1.get('height', 0)
    area2 = box2.get('width', 0) * box2.get('height', 0)
    union_area = area1 + area2 - inter_area

    if union_area == 0:
        return 0.0

    return inter_area / union_area


def deduplicate_wheels_by_iou(wheels, iou_threshold=0.4):
    """Remove overlapping wheel detections using Non-Maximum Suppression.

    Keeps highest confidence detection when overlap exceeds threshold.

    Args:
        wheels: List of wheel/axle detection dicts with x, y, width, height, confidence
        iou_threshold: Overlap threshold (0.4 = 40% overlap triggers dedup)

    Returns:
        List of unique wheel detections
    """
    if len(wheels) <= 1:
        return wheels

    sorted_wheels = sorted(wheels, key=lambda w: w.get('confidence', 0), reverse=True)

    unique_wheels = []
    for wheel in sorted_wheels:
        is_duplicate = False
        for kept_wheel in unique_wheels:
            iou = compute_iou(wheel, kept_wheel)
            if iou > iou_threshold:
                is_duplicate = True
                if DEBUG_MODE:
                    print(f"   🔄 Removing duplicate wheel (IoU={iou:.2f}): {wheel}")
                break
        if not is_duplicate:
            unique_wheels.append(wheel)

    return unique_wheels


# ==================== TIMESTAMP CAPTURE ====================

class PostDecodeTimestampCapture:
    """Adds NTP-synchronized timestamps to each frame before inference."""

    def __init__(self, ntpServer=None):
        self.log = logging.getLogger('SSCAPE_ADAPTER_SIDE')
        self.log.setLevel(logging.INFO)
        self.ntpClient = ntplib.NTPClient()
        self.ntpServer = ntpServer
        self.lastTimeSync = None
        self.timeOffset = 0
        self.timestamp_for_next_block = None
        self.fps = 5.0
        self.fps_alpha = 0.75
        self.last_calculated_fps_ts = None
        self.fps_calc_interval = 1
        self.frame_cnt = 0
        # PTS-anchored clock: timestamps come from buffer PTS + a wall-clock
        # epoch captured on the first frame. Keeps stamps synchronized across
        # cameras even when individual pipelines fluctuate in FPS.
        self.epoch = None

    def _get_pts_seconds(self, frame):
        """Read the underlying GstBuffer PTS (ns) from a DL Streamer
        VideoFrame; return seconds, or None if unavailable."""
        pts_ns = None
        try:
            buf = getattr(frame, '_VideoFrame__buffer', None)
            if buf is None:
                buf = getattr(frame, '_buffer', None)
            if buf is not None and hasattr(buf, 'pts'):
                pts_ns = buf.pts
        except Exception:
            pts_ns = None
        if pts_ns is None or pts_ns < 0 or pts_ns == 0xFFFFFFFFFFFFFFFF:
            return None
        return pts_ns / 1e9

    def processFrame(self, frame):
        wall = time.time()
        self.frame_cnt += 1
        if not self.last_calculated_fps_ts:
            self.last_calculated_fps_ts = wall
        if (wall - self.last_calculated_fps_ts) > self.fps_calc_interval:
            self.fps = self.fps * self.fps_alpha + (1 - self.fps_alpha) * (self.frame_cnt / (wall - self.last_calculated_fps_ts))
            self.last_calculated_fps_ts = wall
            self.frame_cnt = 0

        if self.ntpServer:
            if not self.lastTimeSync or wall - self.lastTimeSync > 1000:
                response = self.ntpClient.request(host=self.ntpServer, port=123)
                self.timeOffset = response.offset
                self.lastTimeSync = wall

        # Anchor timestamp to PTS so all cameras (decoded from synchronized
        # recordings) emit identical stamps for the same physical instant.
        pts_s = self._get_pts_seconds(frame)
        if pts_s is not None:
            if self.epoch is None:
                self.epoch = wall - pts_s + self.timeOffset
            now = self.epoch + pts_s
        else:
            now = wall + self.timeOffset
        self.timestamp_for_next_block = now
        frame.add_message(json.dumps({
            'postdecode_timestamp': f"{datetime.fromtimestamp(now, tz=timezone(TIMEZONE)).strftime(DATETIME_FORMAT)[:-3]}Z",
            'timestamp_for_next_block': now,
            'fps': self.fps
        }))
        return True


# ==================== VEHICLE ATTRIBUTE POLICY ====================

def vehicleAttributePolicy(pobj, item, fw, fh, all_detections):
    """Vehicle Attributes policy with ground-contact axle filtering.

    Handles vehicle type, color, and axle counting.
    """
    label = item.get('label', '')
    label_lower = str(label).lower() if label else ''
    vehicle_type_found = False

    # Check top-level label for vehicle type
    if label_lower in VEHICLE_TYPES:
        pobj['category'] = 'vehicle'
        pobj['vehicle_type'] = label_lower
        pobj['raw_label'] = label
        vehicle_type_found = True

    # Check tensors for vehicle type
    tensors_list = item.get('tensors') or item.get('tensor') or []
    if not vehicle_type_found and tensors_list:
        for tensor in tensors_list:
            tensor_label = str(tensor.get('label', '')).lower()
            if tensor_label in VEHICLE_TYPES:
                pobj['category'] = 'vehicle'
                pobj['vehicle_type'] = tensor_label
                pobj['raw_label'] = tensor.get('label', '')
                pobj['confidence'] = tensor.get('confidence') or 0.99
                vehicle_type_found = True
                break

    # Handle axle detections
    if label_lower == 'axle' or (not vehicle_type_found and
        any(str(t.get('label', '')).lower() == 'axle' for t in tensors_list)):
        pobj['category'] = 'axle'
        pobj['raw_label'] = 'axle'
        pobj['confidence'] = item.get('confidence') or 0.99
        if all(k in item for k in ('x', 'y', 'width', 'height')):
            pobj['bounding_box_px'] = {
                'x': item['x'], 'y': item['y'],
                'width': item['width'], 'height': item['height']
            }
        return

    if not vehicle_type_found:
        pobj['category'] = 'vehicle'

    raw_conf = item.get('confidence')
    pobj['confidence'] = raw_conf if raw_conf and raw_conf > 0 else 0.99

    # Bounding box
    if all(k in item for k in ('x', 'y', 'width', 'height')):
        pobj['bounding_box_px'] = {
            'x': item['x'], 'y': item['y'],
            'width': item['width'], 'height': item['height']
        }
        x, y, w, h = item['x'], item['y'], item['width'], item['height']
        pobj['center_of_mass'] = {
            'x': int(x + w / 3),
            'y': int(y + h / 4),
            'width': w / 3,
            'height': h / 4
        }

    # Extract color
    if 'tensor' in item or 'tensors' in item:
        for tensor in item.get('tensors') or item.get('tensor') or []:
            tensor_label = str(tensor.get('label', '')).lower()
            if tensor_label in COLOR_LABELS:
                pobj['vehicle_color'] = tensor_label
                break

    # Find axles associated with this vehicle (with deduplication)
    vehicle_obj_id = item.get('object_id')
    vehicle_axles = []
    seen_axle_ids = set()

    AXLE_CONFIDENCE_THRESHOLD = 0.7  # Reject axle detections below 50% confidence

    for det in all_detections:
        det_label = str(det.get('label', '')).lower()
        if det_label == 'axle':
            # Filter out low-confidence false positives (license plates, tail lights, etc.)
            det_confidence = det.get('confidence', 0)
            if det_confidence < AXLE_CONFIDENCE_THRESHOLD:
                if DEBUG_MODE:
                    print(f"   ⛔ Rejected axle detection: confidence={det_confidence:.0%} < {AXLE_CONFIDENCE_THRESHOLD:.0%}")
                continue

            det_id = det.get('object_id') or det.get('id') or id(det)

            if det_id in seen_axle_ids:
                continue

            belongs_to_vehicle = False
            if det.get('parent_id') == vehicle_obj_id and vehicle_obj_id is not None:
                belongs_to_vehicle = True
            elif is_axle_inside_vehicle(det, item):
                belongs_to_vehicle = True

            if belongs_to_vehicle:
                vehicle_axles.append(det)
                seen_axle_ids.add(det_id)

    # Deduplicate overlapping axle detections (IoU > 65% = same tyre)
    if vehicle_axles:
        before_count = len(vehicle_axles)
        vehicle_axles = deduplicate_wheels_by_iou(vehicle_axles, iou_threshold=0.65)
        if DEBUG_MODE and before_count != len(vehicle_axles):
            print(f"   🔄 IoU dedup: {before_count} → {len(vehicle_axles)} axles (removed {before_count - len(vehicle_axles)} duplicates)")

    # Calculate ground level and classify axles
    if vehicle_axles:
        ground_y = get_ground_level(item, vehicle_axles)
        # Scale tolerance to the vehicle's bbox height so the threshold adapts
        # to zoom / vehicle size instead of being a fixed 80 px slack. Floor at
        # 25 px so tiny far-away vehicles still get a workable margin.
        vehicle_height_px = item.get('height', 0) or 0
        tolerance = max(25, int(0.08 * vehicle_height_px))

        classified_axles = classify_axles_ground_contact(vehicle_axles, ground_y, tolerance)

        touching_count = sum(1 for a in classified_axles if a['touching_ground'])
        not_touching_count = len(classified_axles) - touching_count

        pobj['axle_count'] = len(classified_axles)
        pobj['wheel_count'] = len(classified_axles) * 2
        pobj['touching_ground'] = touching_count
        pobj['not_touching_ground'] = not_touching_count
        pobj['wheels_touching_ground'] = touching_count * 2
        pobj['wheels_not_touching_ground'] = not_touching_count * 2
        pobj['axles'] = classified_axles
        pobj['ground_y'] = ground_y
    else:
        pobj['axle_count'] = 0
        pobj['wheel_count'] = 0
        pobj['touching_ground'] = 0
        pobj['not_touching_ground'] = 0
        pobj['axles'] = []


metadatapolicies = {
    "vehicleAttributePolicy": vehicleAttributePolicy
}


# ==================== DATA PUBLISHER ====================

class PostInferenceDataPublish:
    """Publishes vehicle/axle inference data to MQTT."""

    def __init__(self, cameraid, metadatagenpolicy='vehicleAttributePolicy', publish_image=False, view_angle='left'):
        self.log = logging.getLogger('SSCAPE_ADAPTER_SIDE')
        self.log.setLevel(logging.INFO)
        self.cameraid = cameraid
        self.view_angle = view_angle if view_angle else 'left'
        self.is_publish_image = publish_image
        self.is_publish_calibration_image = False
        self.setupMQTT()
        self.metadatagenpolicy = vehicleAttributePolicy
        self.frame_level_data = {'id': cameraid, 'debug_mac': getMACAddress()}

        # ==================== MAX TRACKING MEMORY ====================
        # Stores the best-known data per vehicle across frames.
        # Key: object_id  →  Value: {
        #     'max_axle_count': int,         ← highest axle count ever seen
        #     'best_axle_data': dict,        ← full axle metadata from best frame
        #     'best_side_view_b64': str,     ← image from best frame
        #     'last_seen': float             ← timestamp for TTL cleanup
        # }
        self.vehicle_memory = {}
        self.log.info("MAX TRACKING enabled: will remember peak axle count + best image per vehicle")

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to MQTT Broker {self.broker}")
            self.client.subscribe(f"scenescape/cmd/camera/{self.cameraid}")
            print(f"Subscribed to topic: scenescape/cmd/camera/{self.cameraid}")
        else:
            print(f"Failed to connect, return code {rc}")

    def setupMQTT(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.broker = os.environ.get('MQTT_BROKER', 'broker.scenescape.intel.com')
        try:
            self.client.connect(self.broker, int(os.environ.get('MQTT_PORT', '1883')), 120)
        except Exception as e:
            self.log.error(f"Failed to connect to MQTT broker {self.broker}: {e}")
        self.client.on_message = self.handleCameraMessage
        if ROOT_CA and os.path.exists(ROOT_CA):
            self.client.tls_set(ca_certs=ROOT_CA)
        self.client.loop_start()

    def handleCameraMessage(self, client, userdata, message):
        msg = str(message.payload.decode("utf-8"))
        if msg == "getimage":
            self.is_publish_image = True
        elif msg == "getcalibrationimage":
            self.is_publish_calibration_image = True

    def annotateObjects(self, img):
        objColors = ((0, 0, 255), (255, 128, 128), (207, 83, 255), (31, 156, 238))
        for otype, objects in self.frame_level_data.get('objects', {}).items():
            if otype == "person":
                cindex = 0
            elif otype in ("vehicle", "bicycle", "license_plate", "sedan", "truck", "bus"):
                cindex = 1
            else:
                cindex = 2
            for obj in objects:
                try:
                    topleft_cv = (int(obj['bounding_box_px']['x']), int(obj['bounding_box_px']['y']))
                    bottomright_cv = (int(obj['bounding_box_px']['x'] + obj['bounding_box_px']['width']),
                                      int(obj['bounding_box_px']['y'] + obj['bounding_box_px']['height']))
                    cv2.rectangle(img, topleft_cv, bottomright_cv, objColors[cindex], 4)
                except Exception:
                    continue

    def annotateFPS(self, img, fpsval):
        fpsStr = f'FPS {fpsval:.1f}'
        scale = int((img.shape[0] + 479) / 480)
        cv2.putText(img, fpsStr, (0, 30 * scale), cv2.FONT_HERSHEY_SIMPLEX,
                    1 * scale, (0, 0, 0), 5 * scale)
        cv2.putText(img, fpsStr, (0, 30 * scale), cv2.FONT_HERSHEY_SIMPLEX,
                    1 * scale, (255, 255, 255), 2 * scale)

    def buildImgData(self, imgdatadict, gvaframe, annotate):
        """Build image data with error handling for corrupted buffers."""
        imgdatadict.update({
            'timestamp': self.frame_level_data.get('timestamp'),
            'id': self.cameraid
        })
        try:
            with gvaframe.data() as image:
                if annotate:
                    self.annotateObjects(image)
                    self.annotateFPS(image, self.frame_level_data.get('rate', 0.0))
                _, jpeg = cv2.imencode(".jpg", image)
            jpeg = base64.b64encode(jpeg).decode('utf-8')
            imgdatadict['image'] = jpeg
        except RuntimeError as e:
            self.log.error(f"Failed to build image data: {e}")
            imgdatadict['image'] = None

    def _cleanup_stale_vehicles(self, now):
        """Remove vehicles from memory that haven't been seen for VEHICLE_MEMORY_TTL seconds."""
        stale_ids = [
            obj_id for obj_id, mem in self.vehicle_memory.items()
            if (now - mem.get('last_seen', 0)) > VEHICLE_MEMORY_TTL
        ]
        for obj_id in stale_ids:
            if DEBUG_MODE:
                print(f"🗑️ MAX TRACKING: Removing stale vehicle {obj_id} from memory")
            del self.vehicle_memory[obj_id]

    def buildObjData(self, gvadata, frame):
        """Build object data with vehicle/axle-specific logic + MAX TRACKING."""
        if DEBUG_MODE:
            print("🔧 SIDE ADAPTER [MAX TRACKING]: buildObjData")

        now = time.time()
        self.frame_level_data.update({
            'timestamp': gvadata.get('postdecode_timestamp'),
            'debug_timestamp_end': f"{datetime.fromtimestamp(now, tz=timezone(TIMEZONE)).strftime(DATETIME_FORMAT)[:-3]}Z",
            'debug_processing_time': now - float(gvadata.get('timestamp_for_next_block', now)),
            'rate': float(gvadata.get('fps', 0.0))
        })

        # Periodically clean up stale vehicle memory entries
        self._cleanup_stale_vehicles(now)

        objects = defaultdict(list)
        resolution = gvadata.get('resolution', {})
        framewidth = resolution.get('width', 0)
        frameheight = resolution.get('height', 0)

        detections = gvadata.get('objects', None)
        if detections is None:
            detections = gvadata.get('gva_meta', [])

        # Flatten nested detections
        def get_all_detections_recursive(dets):
            all_dets = []
            if not dets:
                return all_dets
            for d in dets:
                all_dets.append(d)
                if 'objects' in d and isinstance(d['objects'], list):
                    all_dets.extend(get_all_detections_recursive(d['objects']))
            return all_dets

        all_flattened_detections = get_all_detections_recursive(detections)

        if DEBUG_MODE:
            print(f"DEBUG: Top-level detections: {len(detections)}")
            print(f"DEBUG: All flattened detections: {len(all_flattened_detections)}")
            labels = [d.get('label') for d in all_flattened_detections]
            print(f"DEBUG: All detection labels: {labels}")

        vehicles_to_process = []

        for det in all_flattened_detections:

            if (det.get("confidence") is None and
                det.get("region_id") == 0 and
                det.get("parent_id") is None ):
                continue

            vaobj = {}

            vehicleAttributePolicy(vaobj, det, framewidth, frameheight, all_flattened_detections)
            vaobj['object_id'] = det.get('object_id')

            category = vaobj.get('category', 'unknown')
            det_label = det.get('label')

            if DEBUG_MODE:
                print(f"   📍 Detection: label='{det_label}' -> category='{category}'")

            if category == 'axle':
                continue

            if category == 'vehicle':
                vaobj['id'] = len(objects['vehicle']) + 1
                objects['vehicle'].append(vaobj)

                if vaobj.get('axle_count', 0) > 0:
                    vehicles_to_process.append(vaobj)
            elif category in ('person', 'pedestrian'):
                vaobj['id'] = len(objects['person']) + 1
                objects['person'].append(vaobj)

        # ==================== MAX TRACKING + IMAGE CAPTURE ====================
        # For each vehicle with axles, apply max-tracking logic:
        #   - If current axle_count >= previous max → update memory (new best frame)
        #   - If current axle_count < previous max → use stored best data
        #   - Image is captured ONLY when axle count is at or above the max
        #     (= vehicle is fully visible), ensuring we never store a half-vehicle image.

        if vehicles_to_process:
            try:
                with frame.data() as image:
                    for vaobj in vehicles_to_process:
                        obj_id = vaobj.get('object_id')
                        current_axle_count = vaobj.get('axle_count', 0)
                        prev_memory = self.vehicle_memory.get(obj_id, {})
                        prev_max_axles = prev_memory.get('max_axle_count', 0)

                        # A side view is only trustworthy when the vehicle is
                        # NOT clipped on left/right edges (axles get cut off
                        # and axle_count is artificially low). Disqualify
                        # edge-clipped frames from updating the best view.
                        bbox = vaobj.get('bounding_box_px') or {}
                        bx = int(bbox.get('x', 0))
                        bw = int(bbox.get('width', 0))
                        EDGE_MARGIN = 8
                        touches_left = bx <= EDGE_MARGIN
                        touches_right = (bx + bw) >= (framewidth - EDGE_MARGIN)
                        is_fully_in_frame = not (touches_left or touches_right)

                        # Update best view only if (a) we have more axles than
                        # before AND the vehicle is fully in frame, OR (b) we
                        # match the previous max axle count AND are fully in
                        # frame (lets a later, better-centered frame win ties).
                        new_max = (current_axle_count > prev_max_axles) and is_fully_in_frame
                        improve_at_max = (current_axle_count == prev_max_axles) and is_fully_in_frame and prev_max_axles > 0
                        # Bootstrap: if we have nothing yet, take whatever we
                        # can get (even edge-clipped) so the message isn't empty.
                        bootstrap = (prev_max_axles == 0) and (prev_memory.get('best_side_view_b64') is None)

                        if new_max or improve_at_max or bootstrap:
                            # ─── NEW BEST or EQUAL: vehicle is fully/more visible ───
                            # Capture the side-view image from THIS frame
                            vehicle_image_b64 = None
                            bbox = vaobj.get('bounding_box_px')
                            if bbox:
                                x = int(bbox.get('x', 0))
                                y = int(bbox.get('y', 0))
                                w = int(bbox.get('width', 0))
                                h = int(bbox.get('height', 0))

                                if w > 0 and h > 0:
                                    vehicle_crop = image[y:y+h, x:x+w]
                                    if vehicle_crop.size > 0:
                                        _, buffer = cv2.imencode('.jpg', vehicle_crop)
                                        vehicle_image_b64 = base64.b64encode(buffer).decode('utf-8')

                            # Update memory with this frame's data
                            self.vehicle_memory[obj_id] = {
                                'max_axle_count': current_axle_count,
                                'best_axle_data': {
                                    'axle_count': vaobj.get('axle_count'),
                                    'wheel_count': vaobj.get('wheel_count'),
                                    'touching_ground': vaobj.get('touching_ground'),
                                    'not_touching_ground': vaobj.get('not_touching_ground'),
                                    'wheels_touching_ground': vaobj.get('wheels_touching_ground'),
                                    'wheels_not_touching_ground': vaobj.get('wheels_not_touching_ground'),
                                    'axles': vaobj.get('axles', []),
                                    'ground_y': vaobj.get('ground_y'),
                                },
                                'best_side_view_b64': vehicle_image_b64,
                                'last_seen': now
                            }

                            # Use current frame's data (it IS the best)
                            vaobj[f"{self.view_angle}_vehicle_side_view_b64"] = vehicle_image_b64

                            if DEBUG_MODE:
                                if new_max:
                                    action = "NEW MAX"
                                elif improve_at_max:
                                    action = "EQUAL (better-framed)"
                                else:
                                    action = "BOOTSTRAP"
                                print(f"📈 MAX TRACKING [{action}]: vehicle {obj_id} "
                                      f"axle_count={current_axle_count} (prev_max={prev_max_axles}) "
                                      f"fully_in_frame={is_fully_in_frame}")
                                if vehicle_image_b64:
                                    print(f"   📸 Best image updated: {len(vehicle_image_b64)} bytes")

                        else:
                            # ─── NOT AN IMPROVEMENT (fewer axles, or clipped) ───
                            # Restore the best-known data from memory
                            best_data = prev_memory.get('best_axle_data', {})
                            vaobj['axle_count'] = best_data.get('axle_count', current_axle_count)
                            vaobj['wheel_count'] = best_data.get('wheel_count', current_axle_count * 2)
                            vaobj['touching_ground'] = best_data.get('touching_ground', vaobj.get('touching_ground', 0))
                            vaobj['not_touching_ground'] = best_data.get('not_touching_ground', vaobj.get('not_touching_ground', 0))
                            vaobj['wheels_touching_ground'] = best_data.get('wheels_touching_ground', vaobj.get('wheels_touching_ground', 0))
                            vaobj['wheels_not_touching_ground'] = best_data.get('wheels_not_touching_ground', vaobj.get('wheels_not_touching_ground', 0))
                            vaobj['axles'] = best_data.get('axles', vaobj.get('axles', []))
                            vaobj['ground_y'] = best_data.get('ground_y', vaobj.get('ground_y'))

                            # Use the stored best image instead of current frame's
                            best_image = prev_memory.get('best_side_view_b64')
                            if best_image:
                                vaobj[f"{self.view_angle}_vehicle_side_view_b64"] = best_image

                            # Update last_seen timestamp (vehicle is still tracked)
                            self.vehicle_memory[obj_id]['last_seen'] = now

                            if DEBUG_MODE:
                                print(f"📉 MAX TRACKING [KEPT BEST]: vehicle {obj_id} "
                                      f"current_axles={current_axle_count} < max={prev_max_axles} "
                                      f"→ using stored best data")

            except Exception as e:
                self.log.error(f"Failed during max tracking / image capture: {e}")

        self.frame_level_data['objects'] = objects

    def processFrame(self, frame):
        """Main frame processing."""
        if self.client.is_connected():
            gvametadata, imgdatadict = {}, {}

            try:
                utils.get_gva_meta_messages(frame, gvametadata)
            except Exception:
                gvametadata = {}

            if gvametadata.get('gva_meta') and 'objects' not in gvametadata:
                gvametadata['objects'] = gvametadata['gva_meta']

            # Normalize detections
            for det in gvametadata.get('objects', []):
                if 'detection' in det:
                    d = det['detection']
                    if 'label' not in det:
                        det['label'] = d.get('label')
                    if 'confidence' not in det:
                        det['confidence'] = d.get('confidence')
                if 'w' in det and 'width' not in det:
                    det['width'] = det['w']
                if 'h' in det and 'height' not in det:
                    det['height'] = det['h']
                if det.get('object_id') is None and det.get('id') is not None:
                    det['object_id'] = det.get('id')

            if DEBUG_MODE:
                print("GVAMETADATA (raw detections):", gvametadata.get('objects', []))

            # Smart label defaulting
            for det in gvametadata.get('objects', []):
                if det.get('label') is None and det.get('object_id') is not None:
                    det['label'] = 'vehicle'

            self.buildObjData(gvametadata, frame)

            # Publish images (only if successfully captured)
            if self.is_publish_image:
                self.buildImgData(imgdatadict, frame, True)
                if imgdatadict.get('image') is not None:
                    self.client.publish(f"scenescape/image/camera/{self.cameraid}", json.dumps(imgdatadict))
                self.is_publish_image = False

            if self.is_publish_calibration_image:
                if not imgdatadict:
                    self.buildImgData(imgdatadict, frame, False)
                if imgdatadict.get('image') is not None:
                    self.client.publish(f"scenescape/image/calibration/camera/{self.cameraid}", json.dumps(imgdatadict))
                self.is_publish_calibration_image = False

            final_payload = json.dumps(self.frame_level_data)
            try:
                if DEBUG_MODE:
                    print("FINAL MQTT PAYLOAD:", json.dumps(self.frame_level_data, indent=2))
                self.client.publish(f"scenescape/data/camera/{self.cameraid}", final_payload)
            except Exception as e:
                self.log.error(f"Failed to publish to MQTT: {e}")

            try:
                frame.add_message(final_payload)
            except Exception:
                pass

        return True
