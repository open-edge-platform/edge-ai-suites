# =============================================================================
# Smart Tolling SceneScape Adapter - LPR (Front/Rear Cameras)
# =============================================================================
# Complete standalone adapter for License Plate Recognition.
# For use with toll-front and toll-rear pipelines.
#
# USAGE in config.json:
#   module=/home/pipeline-server/user_scripts/gvapython/sscape/sscape_adapter_lpr_max_tracking.py
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
# Set to True to merge fragmented OCR detections into full plate text
ENABLE_OCR_MERGE = True
OCR_MERGE_MAX_GAP_PX = 80
OCR_MERGE_MAX_Y_OVERLAP = 0.5
MIN_PLATE_LENGTH = 6


def sanitize_plate_text(text):
    """Remove colons, dots, dashes, and all non-alphanumeric characters from OCR text.
    
    OCR models often misread plate edges, bolts, or dirt as special characters
    like ':', '.', '-', '(', etc. This strips everything except letters and digits.
    """
    if not text:
        return text
    # Keep only alphanumeric characters (letters + digits)
    cleaned = ''.join(c for c in str(text) if c.isalnum())
    return cleaned


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
    if any(ch.isdigit() for ch in lab) and any(ch.isalpha() for ch in lab):
        return 'license_plate'
    if 'plate' in lab or 'english' in lab:
        return 'license_plate'
    if lab in ('vehicle', 'car', 'bus', 'truck', 'van', 'sedan', 'suv', 'motorcycle', 'bicycle'):
        return 'vehicle'
    if lab in ('person', 'pedestrian'):
        return 'pedestrian'
    return 'unknown'


def is_plate_text_valid(plate_text):
    if not plate_text:
        return False
    plate_text = plate_text.strip()
    if len(plate_text) < MIN_PLATE_LENGTH:
        return False
    has_letter = any(c.isalpha() for c in plate_text)
    has_digit = any(c.isdigit() for c in plate_text)
    if not (has_letter and has_digit):
        return False
    return True


# ==================== OCR MERGE UTILITIES ====================

def _bbox_right_x(det):
    return det.get('x', 0) + det.get('width', det.get('w', 0))

def _bbox_left_x(det):
    return det.get('x', 0)

def _bbox_top_y(det):
    return det.get('y', 0)

def _bbox_bottom_y(det):
    return det.get('y', 0) + det.get('height', det.get('h', 0))

def _vertical_overlap_fraction(a, b):
    a_top, a_bottom = _bbox_top_y(a), _bbox_bottom_y(a)
    b_top, b_bottom = _bbox_top_y(b), _bbox_bottom_y(b)
    inter_top = max(a_top, b_top)
    inter_bottom = min(a_bottom, b_bottom)
    inter_h = max(0, inter_bottom - inter_top)
    a_h = max(1, a_bottom - a_top)
    return inter_h / a_h

def merge_ocr_detections(dets, max_gap_px=OCR_MERGE_MAX_GAP_PX, min_vertical_overlap=OCR_MERGE_MAX_Y_OVERLAP):
    """Merge horizontally adjacent OCR fragments into full plate text."""
    if not dets:
        return []
    dets_sorted = sorted([dict(d) for d in dets], key=lambda d: d.get('x', 0))
    merged = []
    curr = dets_sorted[0].copy()
    curr_text = ''
    if 'tensor' in curr and curr['tensor']:
        curr_text = ''.join([str(t.get('label', '')) for t in curr['tensor'] if t.get('label')])
    else:
        curr_text = curr.get('text', '') or ''

    for d in dets_sorted[1:]:
        d_text = ''
        if 'tensor' in d and d['tensor']:
            d_text = ''.join([str(t.get('label', '')) for t in d['tensor'] if t.get('label')])
        else:
            d_text = d.get('text', '') or ''

        gap = d.get('x', 0) - _bbox_right_x(curr)
        v_overlap = _vertical_overlap_fraction(curr, d)

        if gap <= max_gap_px and v_overlap >= min_vertical_overlap:
            curr_text = (curr_text or '') + (d_text or '')
            left = min(_bbox_left_x(curr), _bbox_left_x(d))
            right = max(_bbox_right_x(curr), _bbox_right_x(d))
            top = min(_bbox_top_y(curr), _bbox_top_y(d))
            bottom = max(_bbox_bottom_y(curr), _bbox_bottom_y(d))
            curr['x'] = int(left)
            curr['y'] = int(top)
            curr['width'] = int(right - left)
            curr['height'] = int(bottom - top)
            # FIX B: Preserve object_id during OCR merge
            curr['object_id'] = curr.get('object_id') or d.get('object_id') or None
        else:
            if curr_text:
                curr['tensor'] = [{'name': 'classification', 'label': curr_text, 'confidence': 0.0}]
                curr['merged_text'] = curr_text
            merged.append(curr)
            curr = d.copy()
            curr_text = d_text

    if curr_text:
        curr['tensor'] = [{'name': 'classification', 'label': curr_text, 'confidence': 0.0}]
        curr['merged_text'] = curr_text
    merged.append(curr)
    return merged



# ==================== TIMESTAMP CAPTURE ====================

class PostDecodeTimestampCapture:
    """Adds NTP-synchronized timestamps to each frame before inference"""
    
    def __init__(self, ntpServer=None):
        self.log = logging.getLogger('SSCAPE_ADAPTER_LPR')
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
        # epoch captured on the first frame. This keeps stamps synchronized
        # across cameras even when individual pipelines fluctuate in FPS.
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


# ==================== LPR POLICY ====================

def detectionPolicy(pobj, item, fw, fh):
    if 'detection' in item:
        # FIX A: Prevent 0.0 confidence rejection by enforcing a 0.99 hard-floor
        raw_conf = item['detection'].get('confidence')
        pobj.update({
            'category': item['detection'].get('label', 'unknown'),
            'confidence': raw_conf if raw_conf is not None and raw_conf > 0 else 0.99
        })
        x = item.get('x')
        y = item.get('y')
        w = item.get('width') or item.get('w')
        h = item.get('height') or item.get('h')
        computeObjBoundingBoxParams(pobj, fw, fh, x, y, w, h,
                                    item['detection']['bounding_box']['x_min'],
                                    item['detection']['bounding_box']['y_min'],
                                    item['detection']['bounding_box']['x_max'],
                                    item['detection']['bounding_box']['y_max'])
    else:
        label = item.get('label') or item.get('text')
        ocr_text = None
        detection_label = None
        detection_confidence = None
        
        if 'tensor' in item or 'tensors' in item:
            for t in item.get('tensors') or item.get('tensor') or []:
                tensor_name = t.get('name', '')
                tensor_label = t.get('label')
                tensor_confidence = t.get('confidence')
                if tensor_label:
                    if tensor_name == 'detection':
                        detection_label = tensor_label
                        detection_confidence = tensor_confidence
                    elif tensor_name == 'classification':
                        if any(c.isdigit() for c in str(tensor_label)) and any(c.isalpha() for c in str(tensor_label)):
                            ocr_text = tensor_label
                            break
                        if len(str(tensor_label)) >= 4:
                            ocr_text = tensor_label
                            break
        
        if detection_label:
            pobj['category'] = map_label_to_category(detection_label)
            pobj['confidence'] = detection_confidence if detection_confidence else 0.99
        elif ocr_text:
            pobj['category'] = 'license_plate'
            pobj['license_plate_text'] = sanitize_plate_text(str(ocr_text).upper())
            pobj['confidence'] = item.get('confidence', 0.99)
        elif label:
            pobj['category'] = map_label_to_category(label)
            pobj['confidence'] = item.get('confidence', 0.99)
        else:
            pobj['category'] = 'unknown'
            pobj['confidence'] = item.get('confidence', 0.99)
        
        x = item.get('x')
        y = item.get('y')
        w = item.get('width') or item.get('w')
        h = item.get('height') or item.get('h')
        if x is not None and y is not None and w is not None and h is not None:
            computeObjBoundingBoxParams(
                pobj, fw, fh, x, y, w, h,
                xminnorm=x / fw if fw > 0 else 0,
                yminnorm=y / fh if fh > 0 else 0,
                xmaxnorm=(x + w) / fw if fw > 0 else 1,
                ymaxnorm=(y + h) / fh if fh > 0 else 1
            )


def lprPolicy(pobj, item, fw, fh):
    """License Plate Recognition policy"""
    detectionPolicy(pobj, item, fw, fh)
    label = item.get('label')

    if str(label) in ('vehicle', '0') and pobj.get('category') != 'license_plate':
        pobj['category'] = 'vehicle'
    elif label == 'English' or pobj.get('category') == 'license_plate':
        pobj['category'] = 'license_plate'
        ocr_text = item.get('text')
        tensors_list = item.get('tensors') or item.get('tensor') or []
        if not ocr_text and tensors_list:
            for t in tensors_list:
                if t.get('label'):
                    ocr_text = t['label']
                    break
        if not ocr_text:
            for k, v in item.items():
                if k.startswith('classification_layer_name:') and isinstance(v, dict):
                    if v.get('label'):
                        ocr_text = v['label']
                        break
        if ocr_text:
            pobj['license_plate_text'] = sanitize_plate_text(str(ocr_text).upper())


metadatapolicies = {
    "detectionPolicy": detectionPolicy,
    "lprPolicy": lprPolicy
}


# ==================== DATA PUBLISHER ====================

class PostInferenceDataPublish:
    """Publishes LPR inference data to MQTT"""
    
    def __init__(self, cameraid, metadatagenpolicy='lprPolicy', publish_image=False, view_angle='front'):
        self.log = logging.getLogger('SSCAPE_ADAPTER_LPR')
        self.log.setLevel(logging.INFO)
        self.cameraid = cameraid
        self.view_angle = view_angle if view_angle else 'front'
        self.is_publish_image = publish_image
        self.is_publish_calibration_image = False
        self.setupMQTT()
        self.metadatagenpolicy = metadatapolicies.get(metadatagenpolicy, lprPolicy)
        self.frame_level_data = {'id': cameraid, 'debug_mac': getMACAddress()}
        
        self.vehicle_memory = {}
        # FIX C: Increase Tracking Memory to stabilize SceneScape tracks
        self.VEHICLE_MEMORY_TTL = 30.0  # seconds

    def cleanup_memory(self):
        now = time.time()
        stale_ids = [vid for vid, data in self.vehicle_memory.items() if now - data['last_seen'] > self.VEHICLE_MEMORY_TTL]
        for vid in stale_ids:
            if DEBUG_MODE:
                print(f"🧹 LPR: Clearing vehicle {vid} from memory (TTL expired)")
            del self.vehicle_memory[vid]

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
        """Build image data with error handling for corrupted buffers"""
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

    def buildObjData(self, gvadata, frame):
        """Build object data with LPR-specific logic"""
        if DEBUG_MODE:
            print("🔧 LPR ADAPTER: buildObjData")
        
        now = time.time()
        self.frame_level_data.update({
            'timestamp': gvadata.get('postdecode_timestamp'),
            'debug_timestamp_end': f"{datetime.fromtimestamp(now, tz=timezone(TIMEZONE)).strftime(DATETIME_FORMAT)[:-3]}Z",
            'debug_processing_time': now - float(gvadata.get('timestamp_for_next_block', now)),
            'rate': float(gvadata.get('fps', 0.0))
        })

        objects = defaultdict(list)
        resolution = gvadata.get('resolution', {})
        framewidth = resolution.get('width', 0)
        frameheight = resolution.get('height', 0)

        lp_data = {}
        detections = gvadata.get('objects', None)
        if detections is None:
            detections = gvadata.get('gva_meta', [])

        # OCR fragment merging
        if ENABLE_OCR_MERGE and detections:
            ocr_candidates = []
            other_dets = []
            for det in detections:
                has_tensor_label = False
                if 'tensor' in det and det['tensor']:
                    for t in det['tensor']:
                        if t.get('label'):
                            has_tensor_label = True
                            break
                if has_tensor_label and (det.get('object_id') is None or det.get('width', det.get('w', 0)) < (framewidth * 0.5)):
                    ocr_candidates.append(det)
                else:
                    other_dets.append(det)
            if ocr_candidates:
                merged = merge_ocr_detections(ocr_candidates)
                detections = other_dets + merged

        all_objects_by_id = {det.get('object_id'): det for det in detections if det.get('object_id') is not None}

        for det in detections:
            parent_id = det.get('parent_id')
            if det.get('label') == 'character' and parent_id is not None:
                parent_lp = all_objects_by_id.get(parent_id)
                if parent_lp:
                    if parent_id not in lp_data:
                        lp_data[parent_id] = {'text': '', 'confidence': []}
                    lp_data[parent_id]['text'] += sanitize_plate_text(det.get('text', ''))
                    if det.get('confidence') is not None:
                        lp_data[parent_id]['confidence'].append(det.get('confidence'))

        vehicle_objects_by_det_id = {}
        plate_detections = []

        for det in detections:
            vaobj = {}
            if det.get('label') in ('English', 'license_plate') and det.get('object_id') in lp_data:
                ocr_text = lp_data[det['object_id']]['text']
                confidences = lp_data[det['object_id']]['confidence']
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                det['text'] = ocr_text
                det['confidence'] = avg_confidence

            self.metadatagenpolicy(vaobj, det, framewidth, frameheight)
            vaobj['object_id'] = det.get('object_id')
            category = vaobj.get('category', 'unknown')
            
            if DEBUG_MODE:
                print(f"   📍 Detection: label='{det.get('label')}' -> category='{category}'")
            
            # if category == 'vehicle':
            #     vaobj['id'] = len(objects['vehicle']) + 1
            #     objects['vehicle'].append(vaobj)
            #     det_obj_id = det.get('object_id')
            #     if det_obj_id is not None:
            #         vehicle_objects_by_det_id[det_obj_id] = vaobj
            if category == 'vehicle':
                # Filter out the ROI container masquerading as a vehicle.
                # A real close-up vehicle is wide but never touches all four
                # frame edges simultaneously; the ROI rectangle does. Only
                # disqualify when the bbox spans the full frame on >=3 sides
                # AND fills most of the frame.
                bbox = vaobj.get('bounding_box_px', {})
                bx, by = bbox.get('x', 0), bbox.get('y', 0)
                bw, bh = bbox.get('width', 0), bbox.get('height', 0)
                if framewidth > 0 and frameheight > 0:
                    edges_touched = sum([
                        bx <= 5,
                        by <= 50,
                        (bx + bw) >= framewidth - 5,
                        (by + bh) >= frameheight - 50,
                    ])
                    fill = (bw * bh) / float(framewidth * frameheight)
                    if edges_touched >= 3 and fill >= 0.70:
                        continue
                
                vaobj['id'] = len(objects['vehicle']) + 1
                objects['vehicle'].append(vaobj)
                det_obj_id = det.get('object_id')
                if det_obj_id is not None:
                    vehicle_objects_by_det_id[det_obj_id] = vaobj
            elif category == 'license_plate':
                if 'license_plate_text' in vaobj:
                    plate_detections.append((det, vaobj))
            elif category in ('person', 'pedestrian'):
                vaobj['id'] = len(objects['person']) + 1
                objects['person'].append(vaobj)

        # Attach plates to vehicles
        def is_bbox_inside(inner_bbox, outer_bbox):
            inner_cx = inner_bbox['x'] + inner_bbox['width'] / 2
            inner_cy = inner_bbox['y'] + inner_bbox['height'] / 2
            return (outer_bbox['x'] <= inner_cx <= outer_bbox['x'] + outer_bbox['width'] and
                    outer_bbox['y'] <= inner_cy <= outer_bbox['y'] + outer_bbox['height'])
        
        def has_invalid_characters(text):
            """Check if plate text contains invalid characters (parentheses, brackets, etc.)"""
            invalid_chars = set('()[]{}@#$%^&*+=<>?/\\|~`:;!\"\',._-')
            return any(c in invalid_chars for c in text)
        
        # Step 1: Filter valid plates and group by matched vehicle
        plates_by_vehicle = {}  # vehicle_id -> list of (det, vaobj, confidence)
        
        for det, vaobj in plate_detections:
            plate_text = vaobj.get('license_plate_text', '')
            plate_bbox = vaobj.get('bounding_box_px')
            parent_id = det.get('parent_id')
            confidence = vaobj.get('confidence', 0)
            
            # Skip plates with invalid characters
            if has_invalid_characters(plate_text):
                if DEBUG_MODE:
                    print(f"❌ Skipping plate with invalid chars: '{plate_text}'")
                continue
            
            # Find matching vehicle
            matched_vehicle = None
            matched_vehicle_id = None
            if parent_id and parent_id in vehicle_objects_by_det_id:
                matched_vehicle = vehicle_objects_by_det_id[parent_id]
                matched_vehicle_id = matched_vehicle.get('object_id')
            else:
                for vehicle in objects.get('vehicle', []):
                    vehicle_bbox = vehicle.get('bounding_box_px')
                    if vehicle_bbox and plate_bbox and is_bbox_inside(plate_bbox, vehicle_bbox):
                        matched_vehicle = vehicle
                        matched_vehicle_id = vehicle.get('object_id')
                        break
            
            if matched_vehicle:
                if matched_vehicle_id not in plates_by_vehicle:
                    plates_by_vehicle[matched_vehicle_id] = []
                plates_by_vehicle[matched_vehicle_id].append((det, vaobj, confidence, matched_vehicle))
            else:
                continue  # Skip plates not matched to any vehicle
        
        # Step 2: For each vehicle, keep only the plate with highest confidence
        best_plates = []
        for vehicle_id, plates in plates_by_vehicle.items():
            # Sort by confidence descending, take the best one
            plates.sort(key=lambda x: x[2], reverse=True)
            best_det, best_vaobj, best_conf, matched_vehicle = plates[0]
            if DEBUG_MODE and len(plates) > 1:
                print(f"🎯 Kept best plate (conf={best_conf:.4f}) out of {len(plates)} candidates for vehicle {vehicle_id}")
            best_plates.append((best_det, best_vaobj, matched_vehicle))
        
        # Step 3: Manage Vehicle Memory & Capture Images
        self.cleanup_memory()

        # Phase 3A: Initialize memory and update vehicle images independently
        for vehicle in objects.get('vehicle', []):
            vid = vehicle.get('object_id')
            if vid is None: continue
            
            if vid not in self.vehicle_memory:
                self.vehicle_memory[vid] = {
                    'best_plate_text': None,
                    'best_plate_confidence': -1.0,
                    'best_plate_image_b64': None,
                    'best_plate_bbox': None,
                    'best_vehicle_image_b64': None,
                    'best_vehicle_score': -1.0,
                    'last_seen': time.time()
                }
            mem = self.vehicle_memory[vid]
            mem['last_seen'] = time.time()

            # ---- Vehicle Image Tracking (quality-scored, not area-only) ----
            # The "best view" of a vehicle is when it is FULLY in frame and
            # reasonably centered, not when it has grown largest (which is
            # typically the moment it's exiting and clipped against an edge).
            #
            # Quality score:
            #   - Hard disqualify if bbox touches any frame edge (returns -1).
            #   - Fill ratio: best when vehicle occupies 20%-65% of the frame.
            #   - Centeredness: bonus the closer the centroid is to the middle.
            #   - Multiplied by detection confidence.
            parent_bbox = vehicle.get('bounding_box_px')
            if parent_bbox:
                parent_x = int(parent_bbox['x'])
                parent_y = int(parent_bbox['y'])
                parent_w = int(parent_bbox['width'])
                parent_h = int(parent_bbox['height'])

                EDGE_MARGIN = 8
                hits_edge = (
                    parent_x <= EDGE_MARGIN
                    or parent_y <= EDGE_MARGIN
                    or parent_x + parent_w >= framewidth - EDGE_MARGIN
                    or parent_y + parent_h >= frameheight - EDGE_MARGIN
                )

                score = -1.0
                if not hits_edge and framewidth > 0 and frameheight > 0:
                    fill = (parent_w * parent_h) / float(framewidth * frameheight)
                    if 0.20 <= fill <= 0.65:
                        size_score = 1.0
                    elif 0.10 <= fill < 0.20 or 0.65 < fill <= 0.80:
                        size_score = 0.6
                    else:
                        size_score = 0.2

                    cx = parent_x + parent_w / 2.0
                    cy = parent_y + parent_h / 2.0
                    dx = abs(cx - framewidth / 2.0) / (framewidth / 2.0)
                    dy = abs(cy - frameheight / 2.0) / (frameheight / 2.0)
                    center_score = max(0.0, 1.0 - (dx + dy) / 2.0)

                    conf = float(vehicle.get('confidence', 0.5) or 0.5)
                    score = conf * size_score * center_score

                if score > mem['best_vehicle_score']:
                    try:
                        with frame.data() as image:
                            vehicle_crop = image[parent_y:parent_y+parent_h, parent_x:parent_x+parent_w]
                            if vehicle_crop.size > 0:
                                _, veh_buffer = cv2.imencode('.jpg', vehicle_crop)
                                mem['best_vehicle_image_b64'] = base64.b64encode(veh_buffer).decode('utf-8')
                                mem['best_vehicle_score'] = score
                                if DEBUG_MODE:
                                    print(f"📸 LPR: NEW best vehicle image for {vid} "
                                          f"(score={score:.3f}, fill={(parent_w*parent_h)/(framewidth*frameheight):.2f})")
                    except Exception as e:
                        self.log.error(f"Failed to crop vehicle: {e}")

        # Phase 3B: Process plates and update plate images independently
        for det, vaobj, matched_vehicle in best_plates:
            if not matched_vehicle: continue
            vid = matched_vehicle.get('object_id')
            if vid not in self.vehicle_memory: continue
            
            mem = self.vehicle_memory[vid]
            plate_text = vaobj.get('license_plate_text')
            plate_bbox = vaobj.get('bounding_box_px')
            current_confidence = vaobj.get('confidence', 0)
            
            # Plate Image Tracking (capture if higher confidence)
            if is_plate_text_valid(plate_text) and current_confidence >= mem['best_plate_confidence']:
                try:
                    with frame.data() as image:
                        plate_abs_x, plate_abs_y = int(plate_bbox['x']), int(plate_bbox['y'])
                        plate_w, plate_h = int(plate_bbox['width']), int(plate_bbox['height'])
                        plate_img_crop = image[plate_abs_y:plate_abs_y+plate_h, plate_abs_x:plate_abs_x+plate_w]
                        
                        if plate_img_crop.size > 0:
                            _, buffer = cv2.imencode('.jpg', plate_img_crop)
                            mem['best_plate_image_b64'] = base64.b64encode(buffer).decode('utf-8')
                            mem['best_plate_confidence'] = current_confidence
                            mem['best_plate_text'] = plate_text
                            mem['best_plate_bbox'] = plate_bbox
                            if DEBUG_MODE:
                                print(f"🎯 LPR: Captured NEW best plate for {vid}: '{plate_text}' (conf={current_confidence:.4f})")
                except Exception as e:
                    self.log.error(f"Failed to crop plate: {e}")

        # Phase 3C: Apply BEST memory data to output payload
        for vehicle in objects.get('vehicle', []):
            vid = vehicle.get('object_id')
            if vid not in self.vehicle_memory: continue
            mem = self.vehicle_memory[vid]

            # Apply Best Vehicle Image (keyed by view_angle to avoid collision on merge)
            if mem['best_vehicle_image_b64']:
                vehicle[f"{self.view_angle}_vehicle_image_b64"] = mem['best_vehicle_image_b64']

            # Apply Best Plate Data (keyed by view_angle so front/rear don't overwrite each other)
            if mem['best_plate_text']:
                plate_obj = {
                    'text': mem['best_plate_text'],
                    'confidence': mem['best_plate_confidence'],
                    'bounding_box_px': mem['best_plate_bbox']
                }
                if mem['best_plate_image_b64']:
                    plate_obj['image_b64'] = mem['best_plate_image_b64']
                vehicle[f"{self.view_angle}_license_plate"] = plate_obj

        self.frame_level_data['objects'] = objects

    def processFrame(self, frame):
        """Main frame processing"""
        if self.client.is_connected():
            gvametadata, imgdatadict = {}, {}

            try:
                utils.get_gva_meta_messages(frame, gvametadata)
            except Exception:
                gvametadata = {}

            existing_objects = gvametadata.get('objects') or gvametadata.get('gva_meta')
            if not existing_objects:
                try:
                    gvametadata['objects'] = utils.get_gva_meta_regions(frame)
                except Exception:
                    gvametadata['objects'] = []
            elif gvametadata.get('gva_meta') and 'objects' not in gvametadata:
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