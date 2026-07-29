
import sqlite3
from datetime import datetime, timedelta, timezone 
import numpy as np
import cv2
import threading
from collections import deque
from pathlib import Path
import os
import requests
import argparse
import sys
import json
import base64
import time
import hashlib
import threading
import math
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS

# Only import OpenVINO if using local inference
try:
    from openvino import Core
    import openvino as ov
except ImportError:
    Core = None
    ov = None

# Initialize the database
def init_db():
    conn = sqlite3.connect("status.db")
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS status")
    c.execute("CREATE TABLE status (doors_latched TEXT, patient_present TEXT, people_present TEXT)")
    c.execute("INSERT INTO status (doors_latched, patient_present, people_present) VALUES ('false', 'false', 'false')")
    c.execute("DROP TABLE IF EXISTS workflow")
    c.execute("CREATE TABLE workflow (pullup_found TEXT, buildcab_found TEXT, shared_window_start TEXT, both_latched_time TEXT, pullup_latched TEXT, buildcab_latched TEXT)")
    c.execute("INSERT INTO workflow (pullup_found, buildcab_found, shared_window_start, both_latched_time, pullup_latched, buildcab_latched) VALUES ('false', 'false', '0', '0', 'false', 'false')")
    c.execute("DROP TABLE IF EXISTS frames")
    c.execute("CREATE TABLE frames (latest_frame BLOB)")
    c.execute("INSERT INTO frames (latest_frame) VALUES (NULL)")
    
    # Add rPPG sessions table
    c.execute("DROP TABLE IF EXISTS rppg_sessions")
    c.execute("""CREATE TABLE rppg_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        session_duration INTEGER,
        heart_rate_avg REAL,
        heart_rate_min REAL,
        heart_rate_max REAL,
        confidence_score REAL,
        raw_signal TEXT,
        graph_data TEXT
    )""")
    
    conn.commit()
    conn.close()


# --- Inference Mode Selection ---

parser = argparse.ArgumentParser(description="NICU Warmer Dashboard")
parser.add_argument('--inference', choices=['local', 'ovms'], default='local', help='Inference mode: local or ovms')
parser.add_argument('--ovms_url', type=str, default='http://localhost:9000', help='OVMS REST endpoint base URL')
source_group = parser.add_mutually_exclusive_group()
source_group.add_argument('-c','--camera', type=int, help='Camera index (webcam). Mutually exclusive with --file.')
source_group.add_argument('-f','--file','--forcefile', dest='video_file', type=str, help='Path to a local video file (e.g. Warmer_Testbed_YTHD.mp4). Mutually exclusive with --camera.')
parser.add_argument('--debug', action='store_true', help='Enable diagnostic debug prints')
parser.add_argument('--performance', action='store_true', help='Enable performance diagnostics (timing, device, model, mode)')
parser.add_argument('--diag', action='store_true', help='Enable per-frame model output diagnostics (use with caution)')
parser.add_argument('--log-every', type=int, default=120, help='When --diag is set, log every N frames (default: 120)')
parser.add_argument('--file-realtime', action='store_true', help='For --file playback, approximate real-time by skipping frames when processing lags.')
parser.add_argument('--no-display', action='store_true', help='Disable OpenCV display window (headless / avoid GUI issues).')
args, unknown = parser.parse_known_args()

# Guidance for common flag misuse: using '-camera' instead of '--camera' or '-c'
misused_flag = None
for token in unknown:
    if token.startswith('-camera'):
        misused_flag = token
        break
if misused_flag:
    print("[WARN] Detected unsupported flag usage '", misused_flag, "'. Use '--camera <path_or_index>' or '-c <path_or_index>'.", sep='')
    print("       Example: python dashboard.py --camera Warmer_Testbed_YTHD.mp4")
    print("       Falling back to default camera index (", parser.get_default('camera'), ") unless overridden correctly.", sep='')

INFERENCE_MODE = args.inference
OVMS_URL = args.ovms_url.rstrip('/')
CAMERA_INDEX = args.camera
VIDEO_FILE = args.video_file
DEBUG_MODE = args.debug
PERFORMANCE_MODE = args.performance
DIAG_MODE = args.diag
LOG_EVERY = max(1, args.log_every)
FILE_REALTIME = args.file_realtime if VIDEO_FILE else False
NO_DISPLAY = args.no_display

# Startup time tracking
STARTUP_TIME_FILE = Path(".startup_time")
HIGHEST_STARTUP_TIME = None
CURRENT_STARTUP_TIME = None

# Initialize Flask app for API
app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

# ---------------- rPPG On-Demand Session State (simple backend extraction) ---------------- #
RPPG_SESSION_ACTIVE = False
RPPG_SESSION_START = None
RPPG_SIGNAL = []  # list of (timestamp, value)
RPPG_LOCK = threading.Lock()


@app.route('/api/rppg', methods=['POST'])
def receive_rppg_data():
    """API endpoint to receive rPPG session results from the web app"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['session_duration', 'heart_rate_avg', 'raw_signal', 'graph_data']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Insert data into database
        conn = sqlite3.connect("status.db")
        c = conn.cursor()
        
        c.execute("""INSERT INTO rppg_sessions 
                     (session_duration, heart_rate_avg, heart_rate_min, heart_rate_max, 
                      confidence_score, raw_signal, graph_data) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (data['session_duration'],
                   data['heart_rate_avg'],
                   data.get('heart_rate_min'),
                   data.get('heart_rate_max'),
                   data.get('confidence_score', 0.5),
                   json.dumps(data['raw_signal']),
                   json.dumps(data['graph_data'])))
        
        conn.commit()
        session_id = c.lastrowid
        conn.close()
        
        print(f"rPPG session saved with ID: {session_id}, Heart Rate: {data['heart_rate_avg']} BPM")
        
        return jsonify({
            'success': True, 
            'session_id': session_id,
            'message': 'rPPG data saved successfully'
        }), 200
        
    except Exception as e:
        print(f"Error saving rPPG data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rppg/latest', methods=['GET'])
def get_latest_rppg():
    """API endpoint to get the latest rPPG session data"""
    try:
        conn = sqlite3.connect("status.db")
        c = conn.cursor()
        
        c.execute("""SELECT * FROM rppg_sessions 
                     ORDER BY timestamp DESC LIMIT 1""")
        row = c.fetchone()
        conn.close()
        
        if row:
            columns = ['id', 'timestamp', 'session_duration', 'heart_rate_avg', 
                      'heart_rate_min', 'heart_rate_max', 'confidence_score', 
                      'raw_signal', 'graph_data']
            result = dict(zip(columns, row))
            # Add epoch numeric for easier local time formatting on clients
            try:
                # If timestamp already looks numeric
                if isinstance(result['timestamp'], (int, float)) or str(result['timestamp']).isdigit():
                    ts_epoch = float(result['timestamp'])
                else:
                    # Attempt parse as ISO
                    from datetime import datetime
                    ts_epoch = datetime.fromisoformat(str(result['timestamp'])).timestamp()
                result['timestamp_epoch'] = ts_epoch
            except Exception:
                pass
            
            # Parse JSON fields
            if result['raw_signal']:
                result['raw_signal'] = json.loads(result['raw_signal'])
            if result['graph_data']:
                result['graph_data'] = json.loads(result['graph_data'])
                
            return jsonify(result), 200
        else:
            return jsonify({'message': 'No rPPG sessions found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------- Additional Helper Functions for API (Migration Phase 1) ---------------- #
def _bool_from_text(val: str) -> bool:
    return val == 'true'

def get_status_dict():
    conn = sqlite3.connect("status.db")
    c = conn.cursor()
    c.execute("SELECT doors_latched, patient_present, people_present FROM status")
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    doors_latched, patient_present, people_present = row
    return {
        'doors_latched': _bool_from_text(doors_latched),
        'patient_present': _bool_from_text(patient_present),
        'people_present': _bool_from_text(people_present)
    }

def get_workflow_dict():
    conn = sqlite3.connect("status.db")
    c = conn.cursor()
    c.execute("""
        SELECT pullup_found, buildcab_found, shared_window_start, both_latched_time, 
               pullup_latched, buildcab_latched 
        FROM workflow
    """)
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    pullup_found, buildcab_found, shared_window_start, both_latched_time, pullup_latched, buildcab_latched = row
    def norm_ts(ts):
        return None if ts in (None, '0', '') else ts
    return {
        'pullup_found': _bool_from_text(pullup_found),
        'buildcab_found': _bool_from_text(buildcab_found),
        'shared_window_start': norm_ts(shared_window_start),
        'both_latched_time': norm_ts(both_latched_time),
        'pullup_latched': _bool_from_text(pullup_latched),
        'buildcab_latched': _bool_from_text(buildcab_latched)
    }

def get_latest_frame_bytes():
    # Prefer in-memory cache (fast path)
    with _LATEST_FRAME_LOCK:
        if _LATEST_FRAME_BYTES:
            return _LATEST_FRAME_BYTES

    conn = sqlite3.connect("status.db")
    c = conn.cursor()
    c.execute("SELECT latest_frame FROM frames")
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    frame_blob = row[0]
    if not frame_blob or frame_blob == b'None':
        return None
    return frame_blob

def get_latest_rppg_core():
    conn = sqlite3.connect("status.db")
    c = conn.cursor()
    c.execute("SELECT * FROM rppg_sessions ORDER BY timestamp DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    columns = ['id', 'timestamp', 'session_duration', 'heart_rate_avg', 
               'heart_rate_min', 'heart_rate_max', 'confidence_score', 
               'raw_signal', 'graph_data']
    data = dict(zip(columns, row))
    try:
        data['raw_signal'] = json.loads(data['raw_signal']) if data['raw_signal'] else []
    except Exception:
        data['raw_signal'] = []
    return data

def build_waveform(raw_signal, max_points=400):
    if not raw_signal:
        return []
    n = len(raw_signal)
    if n <= max_points:
        return raw_signal
    step = max(1, n // max_points)
    return raw_signal[::step]

from telemetry_rppg import (
    record_model_inference as _record_model_inference,
    set_all_models_waiting as _set_all_models_waiting,
    model_stats_snapshot as _model_stats_snapshot,
    compute_rppg_metrics as _compute_rppg_metrics,
    RPPG_TARGET_DURATION
)

# ---------------- New API Endpoints (Phase 1) ---------------- #
@app.route('/api/status', methods=['GET'])
def api_status():
    data = get_status_dict()
    if data is None:
        return jsonify({'error': 'status not initialized'}), 404
    return jsonify(data)

@app.route('/api/workflow', methods=['GET'])
def api_workflow():
    data = get_workflow_dict()
    if data is None:
        return jsonify({'error': 'workflow not initialized'}), 404
    return jsonify(data)

@app.route('/api/frame', methods=['GET'])
def api_frame():
    frame_bytes = get_latest_frame_bytes()
    if frame_bytes is None:
        return jsonify({'error': 'no frame available'}), 404
    # Base64 mode
    if request.args.get('base64'):
        b64 = base64.b64encode(frame_bytes).decode('utf-8')
        return jsonify({'image': 'data:image/jpeg;base64,' + b64})
    # Binary response
    return Response(frame_bytes, mimetype='image/jpeg')

@app.route('/api/rppg/waveform', methods=['GET'])
def api_rppg_waveform():
    latest = get_latest_rppg_core()
    if latest is None:
        return jsonify({'error': 'no rPPG data'}), 404
    raw_signal = latest.get('raw_signal', [])
    downsampled = build_waveform(raw_signal)
    return jsonify({
        'session_id': latest['id'],
        'timestamp': latest['timestamp'],
        'total_samples': len(raw_signal),
        'returned_samples': len(downsampled),
        'samples': downsampled
    })

@app.route('/api/health', methods=['GET'])
def api_health():
    try:
        conn = sqlite3.connect("status.db")
        c = conn.cursor()
        c.execute('SELECT 1')
        conn.close()
        return jsonify({'ok': True, 'message': 'healthy'}), 200
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/images/<path:filename>')
def serve_state_image(filename):
    # Serve image assets from local images directory for frontend
    base_dir = Path(__file__).parent / 'images'
    target = base_dir / filename
    if not target.exists():
        return Response(status=404)
    return send_from_directory(base_dir, filename)

@app.route('/api/debug/models', methods=['GET'])
def api_debug_models():
    startup_info = {
        'highest_startup_time': HIGHEST_STARTUP_TIME,
        'current_startup_time': CURRENT_STARTUP_TIME
    }
    return jsonify({
        'models': _model_stats_snapshot(), 
        'ts': time.time(), 
        'action_labels': LAST_ACTION_LABELS, 
        'action_probs': LAST_ACTION_PROBS,
        'startup_times': startup_info
    })

# ---------------- SSE Stream (Phase 2 real-time without WebSockets) ---------------- #
_last_stream_payload = None
_last_waveform_len = 0  # track raw_signal length used for incremental waveform diff
LAST_ACTION_LABELS = []  # updated in action recognition loop
LAST_ACTION_PROBS = []
CURRENT_FRAME_IDX = 0  # current video frame index
VIDEO_LOOP_COUNT = 0  # number of times video has looped

# Latest frame cache (in-memory) to avoid storing large JPEG blobs in SQLite per frame.
_LATEST_FRAME_BYTES = None  # type: bytes | None
_LATEST_FRAME_SEQ = 0
_LATEST_FRAME_LOCK = threading.Lock()

def _set_latest_frame_bytes(frame_bytes: bytes):
    global _LATEST_FRAME_BYTES, _LATEST_FRAME_SEQ
    with _LATEST_FRAME_LOCK:
        _LATEST_FRAME_BYTES = frame_bytes
        _LATEST_FRAME_SEQ += 1

def _get_latest_frame_marker():
    with _LATEST_FRAME_LOCK:
        return _LATEST_FRAME_SEQ if _LATEST_FRAME_BYTES else None

def build_stream_snapshot():
    status = get_status_dict()
    workflow = get_workflow_dict()
    rppg_core = get_latest_rppg_core()
    waveform = None
    waveform_append = None
    rppg_metrics = None
    if rppg_core:
        raw_signal = rppg_core.get('raw_signal', [])
        global _last_waveform_len
        # Full (downsampled) snapshot only when session inactive or on first send
        waveform_samples = None
        if not RPPG_SESSION_ACTIVE:
            # Provide full (downsampled) waveform for completed session context
            waveform_samples = build_waveform(raw_signal, max_points=250)
            waveform = {
                'session_id': rppg_core['id'],
                'timestamp': rppg_core['timestamp'],
                'returned_samples': len(waveform_samples),
                'samples': waveform_samples,
                'total_samples': len(raw_signal)
            }
            _last_waveform_len = len(raw_signal)
        else:
            # Session active: emit only new raw samples (un-downsampled) since last length
            cur_len = len(raw_signal)
            if cur_len > _last_waveform_len:
                new_segment = raw_signal[_last_waveform_len:cur_len]
                waveform_append = {
                    'session_id': rppg_core['id'],
                    'append': new_segment,
                    'total_samples': cur_len
                }
                _last_waveform_len = cur_len
        # Provide also epoch for frontend local-time rendering
        ts_epoch = None
        try:
            if isinstance(rppg_core['timestamp'], (int, float)) or str(rppg_core['timestamp']).isdigit():
                ts_epoch = float(rppg_core['timestamp'])
            else:
                from datetime import datetime
                ts_epoch = datetime.fromisoformat(str(rppg_core['timestamp'])).timestamp()
        except Exception:
            ts_epoch = None
        rppg_metrics = {
            'id': rppg_core['id'],
            'timestamp': rppg_core['timestamp'],
            'timestamp_epoch': ts_epoch,
            'session_duration': rppg_core.get('session_duration'),
            'heart_rate_avg': rppg_core.get('heart_rate_avg'),
            'heart_rate_min': rppg_core.get('heart_rate_min'),
            'heart_rate_max': rppg_core.get('heart_rate_max'),
            'confidence_score': rppg_core.get('confidence_score')
        }
    # Frame freshness (avoid pushing binary in SSE) -> just time marker if exists
    frame_marker = _get_latest_frame_marker()
    frame_b64 = None
    # Base64-inlining frames inside SSE is expensive and tends to dominate CPU/network.
    # Keep it opt-in for debugging.
    if os.environ.get('SSE_FRAME_INLINE', '').lower() in ('1', 'true', 'yes'):
        frame_bytes = get_latest_frame_bytes()
        if frame_bytes:
            frame_b64 = 'data:image/jpeg;base64,' + base64.b64encode(frame_bytes).decode('utf-8')
    with RPPG_LOCK:
        if RPPG_SESSION_ACTIVE and RPPG_SESSION_START:
            rppg_elapsed = int(time.time() - RPPG_SESSION_START)
        else:
            rppg_elapsed = 0
    base = {
        'status': status,
        'workflow': workflow,
        'rppg_metrics': rppg_metrics,
        'waveform': waveform,
        'frame_marker': frame_marker,
        'frame_inline': frame_b64,
        'rppg_active': RPPG_SESSION_ACTIVE,
        'rppg_elapsed': rppg_elapsed,
        'model_stats': _model_stats_snapshot(),
        'video_frame_idx': CURRENT_FRAME_IDX,
        'video_loop_count': VIDEO_LOOP_COUNT,
        'ts': int(time.time())
    }
    if waveform_append:
        base['waveform_append'] = waveform_append
    return base

@app.route('/api/stream')
def api_stream():
    def event_stream():
        global _last_stream_payload
        while True:
            try:
                snap = build_stream_snapshot()
                if snap != _last_stream_payload:
                    _last_stream_payload = snap
                    yield f"data: {json.dumps(snap)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error':'stream_failure','detail':str(e)})}\n\n"
            # Faster tick improves perceived UI smoothness (frame marker updates).
            # Keep modest to avoid unnecessary CPU/network churn.
            time.sleep(float(os.environ.get('SSE_INTERVAL_S', '0.2')))
    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'  # for nginx users
    }
    return Response(event_stream(), mimetype='text/event-stream', headers=headers)

@app.route('/api/rppg/start', methods=['POST'])
def api_rppg_start():
    global RPPG_SESSION_ACTIVE, RPPG_SESSION_START, RPPG_SIGNAL
    with RPPG_LOCK:
        if RPPG_SESSION_ACTIVE:
            return jsonify({'error':'session already active'}), 409
        RPPG_SESSION_ACTIVE = True
        RPPG_SESSION_START = time.time()
        RPPG_SIGNAL = []
    return jsonify({'success': True, 'started_at': RPPG_SESSION_START})

@app.route('/api/rppg/stop', methods=['POST'])
def api_rppg_stop():
    global RPPG_SESSION_ACTIVE, RPPG_SESSION_START, RPPG_SIGNAL
    with RPPG_LOCK:
        if not RPPG_SESSION_ACTIVE:
            return jsonify({'error':'no active session'}), 400
        # Copy signal & session start for processing outside of mutation
        signal_copy = list(RPPG_SIGNAL)
        session_start = RPPG_SESSION_START
        try:
            metrics = _compute_rppg_metrics(signal_copy, session_start)
        except Exception as e:
            if DEBUG_MODE:
                print(f"[DEBUG] rPPG stop metrics computation failed: {e}")
            metrics = None
        # End session regardless to enforce timeout/stop semantics
        RPPG_SESSION_ACTIVE = False
        RPPG_SESSION_START = None
        RPPG_SIGNAL = []
    if metrics is None:
        return jsonify({'error':'insufficient data'}), 422
    # Persist metrics to rppg_sessions table
    try:
        conn = sqlite3.connect("status.db")
        c = conn.cursor()
        c.execute("""INSERT INTO rppg_sessions (session_duration, heart_rate_avg, heart_rate_min, heart_rate_max, confidence_score, raw_signal, graph_data)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (metrics['session_duration'], metrics['heart_rate_avg'], metrics['heart_rate_min'], metrics['heart_rate_max'], metrics['confidence_score'], json.dumps(metrics['raw_signal']), json.dumps(metrics['graph_data'])))
        conn.commit()
        sess_id = c.lastrowid
        conn.close()
        metrics['session_id'] = sess_id
    except Exception as e:
        return jsonify({'error': f'failed to save session: {e}'}), 500
    metrics['started_at'] = session_start
    return jsonify({'success': True, **metrics})

# --- Model and label loading ---
if INFERENCE_MODE == 'local':
    # Load highest startup time observed so far
    if STARTUP_TIME_FILE.exists():
        try:
            HIGHEST_STARTUP_TIME = float(STARTUP_TIME_FILE.read_text().strip())
            print(f"[INFO] Highest startup time observed: {HIGHEST_STARTUP_TIME:.2f}s")
        except:
            pass
    
    # Start timing current startup
    model_load_start = time.time()
    
    core = Core()
    # Enable model caching to speed up subsequent startups
    cache_dir = Path("./model_cache")
    cache_dir.mkdir(exist_ok=True)
    print(f"[INFO] Model cache directory: {cache_dir.absolute()}")
    
    # Load person detection model
    person_model = core.read_model(model="person-detect-fp32.xml", weights="person-detect-fp32.bin")
    compiled_person_model = core.compile_model(model=person_model, device_name="GPU", config={"CACHE_DIR": str(cache_dir)})
    person_output = compiled_person_model.output(0)
    # Load and compile the latch detection model
    latch_model = core.read_model(model="latch-detect-fp32.xml", weights="latch-detect-fp32.bin")
    compiled_latch_model = core.compile_model(model=latch_model, device_name="GPU", config={"CACHE_DIR": str(cache_dir)})
    latch_output = compiled_latch_model.output(0)
    # Load and compile the patient detection model
    patient_model = core.read_model(model="patient-detect-fp32.xml", weights="patient-detect-fp32.bin")
    compiled_patient_model = core.compile_model(model=patient_model, device_name="GPU", config={"CACHE_DIR": str(cache_dir)})
    patient_output = compiled_patient_model.output(0)
    # Action Recognition - decoder
    decoder_model = core.read_model(model="action-recognition-0001-decoder.xml", weights="action-recognition-0001-decoder.bin")
    compiled_decoder_model = core.compile_model(model=decoder_model, device_name="NPU", config={"CACHE_DIR": str(cache_dir)})
    input_key_de = compiled_decoder_model.input(0)
    output_keys_de = compiled_decoder_model.output(0)
    # Action Recognition - encoder
    encoder_model = core.read_model(model="action-recognition-0001-encoder.xml", weights="action-recognition-0001-encoder.bin")
    compiled_encoder_model = core.compile_model(model=encoder_model, device_name="NPU", config={"CACHE_DIR": str(cache_dir)})
    input_key_en = compiled_encoder_model.input(0)
    output_keys_en = compiled_encoder_model.output(0)
    # Get input size - Encoder.
    height_en, width_en = list(input_key_en.shape)[2:]
    # Get input size - Decoder.
    frames2decode = list(input_key_de.shape)[0:][1]
    
    # Calculate current startup time
    CURRENT_STARTUP_TIME = time.time() - model_load_start
    print(f"[INFO] Current startup time: {CURRENT_STARTUP_TIME:.2f}s")
    
    # Update highest if current is higher, otherwise keep previous highest
    if HIGHEST_STARTUP_TIME is None or CURRENT_STARTUP_TIME > HIGHEST_STARTUP_TIME:
        HIGHEST_STARTUP_TIME = CURRENT_STARTUP_TIME
        STARTUP_TIME_FILE.write_text(f"{HIGHEST_STARTUP_TIME:.4f}")
        print(f"[INFO] New highest startup time: {HIGHEST_STARTUP_TIME:.2f}s")
    else:
        # Keep previous highest
        speedup = HIGHEST_STARTUP_TIME / CURRENT_STARTUP_TIME if CURRENT_STARTUP_TIME > 0 else 0
        print(f"[INFO] Startup time vs highest: {speedup:.2f}x faster (best: {HIGHEST_STARTUP_TIME:.2f}s)")
else:
    # For OVMS, set model names and input/output shapes
    # These should match the deployed model names in OVMS
    PERSON_MODEL_NAME = "person-detect-fp32"
    LATCH_MODEL_NAME = "latch-detect-fp32"
    PATIENT_MODEL_NAME = "patient-detect-fp32"
    ENCODER_MODEL_NAME = "action-recognition-0001-encoder"
    DECODER_MODEL_NAME = "action-recognition-0001-decoder"
    # Set input/output shapes for preprocessing
    height_en, width_en = 224, 224  # Default, update if needed
    frames2decode = 16  # Default, update if needed

# Action labels - expects in /data
vocab_file_path = Path("data/kinetics.txt")
with vocab_file_path.open(mode="r") as f:
    labels = [line.strip() for line in f]


def ovms_infer(model_name, inputs, signature_name="serving_default"):
    """
    Perform inference via OVMS REST API.
    Args:
        model_name: Name of the model in OVMS
        inputs: Dict of input_name: np.ndarray
        signature_name: (optional) signature name
    Returns:
        Dict of output_name: np.ndarray
    """
    url = f"{OVMS_URL}/v1/models/{model_name}:predict"
    data = {"inputs": {k: v.tolist() for k, v in inputs.items()}}
    import time
    start_time = time.time()
    try:
        resp = requests.post(url, json=data)
        resp.raise_for_status()
        result = resp.json()
        elapsed = time.time() - start_time
        if PERFORMANCE_MODE:
            print(f"[PERF] Inference: device=OVMS, model={model_name}, mode=ovms, time={elapsed:.3f}s")
        if isinstance(result, dict):
            return {k: np.array(v) for k, v in result.get("outputs", result).items()}
        elif isinstance(result, list):
            return {"output": np.array(result)}
        else:
            print(f"OVMS unexpected response type for {model_name}: {type(result)}")
            return None
    except Exception as e:
        elapsed = time.time() - start_time
        if PERFORMANCE_MODE:
            print(f"[PERF] Inference: device=OVMS, model={model_name}, mode=ovms, time={elapsed:.3f}s [ERROR]")
        print(f"OVMS inference error for {model_name}: {e}")
        return None

#Action Recognition Helper Functions
def center_crop(frame: np.ndarray) -> np.ndarray:
    """
    Center crop squared the original frame to standardize the input image to the encoder model

    :param frame: input frame
    :returns: center-crop-squared frame
    """
    img_h, img_w, _ = frame.shape
    min_dim = min(img_h, img_w)
    start_x = int((img_w - min_dim) / 2.0)
    start_y = int((img_h - min_dim) / 2.0)
    roi = [start_y, (start_y + min_dim), start_x, (start_x + min_dim)]
    return frame[start_y : (start_y + min_dim), start_x : (start_x + min_dim), ...], roi

def adaptive_resize(frame: np.ndarray, size: int) -> np.ndarray:
    """
     The frame going to be resized to have a height of size or a width of size

    :param frame: input frame
    :param size: input size to encoder model
    :returns: resized frame, np.array type
    """
    h, w, _ = frame.shape
    scale = size / min(h, w)
    w_scaled, h_scaled = int(w * scale), int(h * scale)
    if w_scaled == w and h_scaled == h:
        return frame
    return cv2.resize(frame, (w_scaled, h_scaled))

def decode_output(probs: np.ndarray, labels: np.ndarray, top_k: int = 3) -> np.ndarray:
    """
    Decodes top probabilities into corresponding label names

    :param probs: confidence vector for 400 actions
    :param labels: list of actions
    :param top_k: The k most probable positions in the list of labels
    :returns: decoded_labels: The k most probable actions from the labels list
              decoded_top_probs: confidence for the k most probable actions
    """
    top_ind = np.argsort(-1 * probs)[:top_k]
    out_label = np.array(labels)[top_ind.astype(int)]
    decoded_labels = [out_label[0][0], out_label[0][1], out_label[0][2]]
    top_probs = np.array(probs)[0][top_ind.astype(int)]
    decoded_top_probs = [top_probs[0][0], top_probs[0][1], top_probs[0][2]]
    return decoded_labels, decoded_top_probs

def preprocessing(frame: np.ndarray, size: int) -> np.ndarray:
    """
    Preparing frame before Encoder.
    The image should be scaled to its shortest dimension at "size"
    and cropped, centered, and squared so that both width and
    height have lengths "size". The frame must be transposed from
    Height-Width-Channels (HWC) to Channels-Height-Width (CHW).

    :param frame: input frame
    :param size: input size to encoder model
    :returns: resized and cropped frame
    """
    # Adaptative resize
    preprocessed = adaptive_resize(frame, size)
    # Center_crop
    (preprocessed, roi) = center_crop(preprocessed)
    # Transpose frame HWC -> CHW
    preprocessed = preprocessed.transpose((2, 0, 1))[None,]  # HWC -> CHW
    return preprocessed, roi

def encoder(preprocessed: np.ndarray, compiled_model=None) -> list:
    """
    Encoder Inference per frame. Calls local or OVMS encoder model.
    """
    start_time = time.time()
    if INFERENCE_MODE == 'local':
        output_key_en = compiled_model.output(0)
        infer_result_encoder = infer_with_retry(compiled_model, preprocessed, output_key_en, 'encoder')
        elapsed = time.time() - start_time
        if PERFORMANCE_MODE:
            print(f"[PERF] Inference: device=NPU, model={ENCODER_MODEL_NAME}, mode=local, time={elapsed:.3f}s")
        return infer_result_encoder
    else:
        input_name = "0"
        result = ovms_infer(ENCODER_MODEL_NAME, {input_name: preprocessed})
        elapsed = time.time() - start_time
        if PERFORMANCE_MODE:
            print(f"[PERF] Inference: device=OVMS, model={ENCODER_MODEL_NAME}, mode=ovms, time={elapsed:.3f}s")
        if result:
            output = list(result.values())[0]
            if output.ndim == 1:
                output = output[np.newaxis, :]
            return output
        else:
            return np.zeros((1, 512), dtype=np.float32)

def decoder(encoder_output: list, compiled_model_de=None) -> list:
    """
    Decoder inference per set of frames. Calls local or OVMS decoder model.
    """
    decoder_input = np.concatenate(encoder_output, axis=0)
    # Defensive shape check before transpose
    if decoder_input.ndim == 4 and decoder_input.shape[3] == 1:
        decoder_input = decoder_input.transpose((2, 0, 1, 3))
        decoder_input = np.squeeze(decoder_input, axis=3)
    elif decoder_input.ndim == 3:
        # Already squeezed
        pass
    else:
        print(f"Warning: Unexpected decoder_input shape: {decoder_input.shape}")
        return ["error", "error", "error"], [0, 0, 0]
    start_time = time.time()
    if INFERENCE_MODE == 'local':
        output_key_de = compiled_model_de.output(0)
        result_de = infer_with_retry(compiled_model_de, decoder_input, output_key_de, 'decoder')
        elapsed = time.time() - start_time
        if PERFORMANCE_MODE:
            print(f"[PERF] Inference: device=NPU, model={DECODER_MODEL_NAME}, mode=local, time={elapsed:.3f}s")
    else:
        input_name = "0"
        result = ovms_infer(DECODER_MODEL_NAME, {input_name: decoder_input})
        elapsed = time.time() - start_time
        if PERFORMANCE_MODE:
            print(f"[PERF] Inference: device=OVMS, model={DECODER_MODEL_NAME}, mode=ovms, time={elapsed:.3f}s")
        if result:
            result_de = list(result.values())[0]
        else:
            result_de = np.zeros((1, 400), dtype=np.float32)
    probs = softmax(result_de - np.max(result_de))
    decoded_labels, decoded_top_probs = decode_output(probs, labels, top_k=3)
    return decoded_labels, decoded_top_probs

def softmax(x: np.ndarray) -> np.ndarray:
    """
    Normalizes logits to get confidence values along specified axis
    x: np.array, axis=None
    """
    exp = np.exp(x)
    return exp / np.sum(exp, axis=None)

def compute_iou(boxA, boxB):
    # boxA and boxB are (x_min, y_min, x_max, y_max)
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    if interArea == 0:
        return 0.0

    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    iou = interArea / float(boxAArea + boxBArea - interArea)
    return iou

def filter_overlapping_boxes(boxes, iou_threshold=0.5):
    # boxes: list of (x_min, y_min, x_max, y_max, confidence)
    boxes = sorted(boxes, key=lambda x: x[4], reverse=True)
    filtered = []

    while boxes:
        best = boxes.pop(0)
        filtered.append(best)
        boxes = [box for box in boxes if compute_iou(best[:4], box[:4]) < iou_threshold]

    return filtered

# --- Robust Inference Helper to mitigate 'Infer Request is busy' ---
def infer_with_retry(compiled_model, input_array, output_port, tag: str, retries: int = 3, backoff: float = 0.01):
    """Attempt inference with small sleep-retry loop if Infer Request is busy."""
    for attempt in range(retries):
        try:
            return compiled_model([input_array])[output_port]
        except RuntimeError as e:
            msg = str(e).lower()
            if 'busy' in msg or 'in use' in msg:
                time.sleep(backoff * (attempt + 1))
                continue
            raise
    # Final attempt without catching to surface persistent failure
    return compiled_model([input_array])[output_port]

# Threaded Main Function to process webcam frames and update database
#######################################################################################

def _resolve_video_file(path_str: str):
    p = Path(path_str.strip().strip('"').strip("'"))
    if not p.is_absolute():
        p = Path.cwd() / p
    return p

def _open_video_capture(is_video_file: bool, source, attempt_ffmpeg: bool = True):
    """Open a cv2.VideoCapture with fallback strategies for Windows/MSMF issues.
    Returns (cap, is_video_file_resolved)."""
    if is_video_file:
        cap = cv2.VideoCapture(source)
        if not cap.isOpened() and attempt_ffmpeg:
            # Try FFMPEG backend (if OpenCV built with it)
            cap.release()
            try:
                cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
            except Exception:
                pass
        return cap, True
    else:
        try:
            idx = int(source) if isinstance(source, str) else source
        except ValueError:
            idx = 0
        cap = cv2.VideoCapture(idx)
        return cap, False

def process_frame():
    global RPPG_SESSION_ACTIVE, RPPG_SESSION_START, RPPG_SIGNAL, VIDEO_LOOP_COUNT, CURRENT_FRAME_IDX
    # Decide source
    if VIDEO_FILE:
        video_path = _resolve_video_file(VIDEO_FILE)
        if DEBUG_MODE:
            print(f"[DEBUG] Requested video file: {video_path} (exists={video_path.exists()})")
        cap, is_video_file = _open_video_capture(True, str(video_path))
        resolved_source = str(video_path)
    else:
        cam_index = 0 if CAMERA_INDEX is None else CAMERA_INDEX
        if DEBUG_MODE:
            print(f"[DEBUG] Requested camera index: {cam_index}")
        cap, is_video_file = _open_video_capture(False, cam_index)
        resolved_source = cam_index

    if DEBUG_MODE:
        mode = 'video_file' if is_video_file else 'camera'
        exists_str = 'n/a'
        if mode == 'video_file':
            exists_str = 'exists' if Path(str(resolved_source)).exists() else 'missing'
        print(f"[DEBUG] Opening source in {mode} mode: {resolved_source} ({exists_str}) diag={'on' if DIAG_MODE else 'off'} every={LOG_EVERY}")
    if not cap or not cap.isOpened():
        if VIDEO_FILE:
            print(f"**ERROR: Unable to open video file '{VIDEO_FILE}' (resolved: {resolved_source}). Verify path/codec.**")
        else:
            print(f"**ERROR: Unable to open camera index '{CAMERA_INDEX if CAMERA_INDEX is not None else 0}'.**")
        return
    action_counter = 0
    encoder_output = []
    decoded_labels = [0, 0, 0]
    decoded_top_probs = [0, 0, 0]
    sample_duration = frames2decode
    size = height_en

    show_display = not NO_DISPLAY
    if show_display:
        try:
            cv2.namedWindow("Press 'q' to quit", cv2.WINDOW_NORMAL)
        except Exception as e:
            print(f"[WARN] Unable to create display window: {e}. Continuing headless.")
            show_display = False

    # Reuse a single SQLite connection for the hot path to avoid per-frame
    # connect/close overhead.
    db_conn = None
    db_cur = None
    try:
        db_conn = sqlite3.connect("status.db", timeout=2.0, check_same_thread=False)
        db_cur = db_conn.cursor()
    except Exception as e:
        print(f"[WARN] Unable to open persistent DB connection: {e}. Falling back to per-frame connections.")
        db_conn = None
        db_cur = None
    # For video-file playback pacing, we treat frame_idx as a count of frames read since
    # the current playback baseline (1-based). Using a monotonic clock avoids NTP/time
    # adjustments causing sudden "lag" spikes and aggressive frame dropping.
    frame_idx = 0
    video_fps = 0.0
    playback_start = None
    max_drop_per_iter = 0
    if is_video_file:
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        if video_fps <= 1 or video_fps > 240:  # fallback if invalid metadata
            video_fps = 30.0
        playback_start = time.perf_counter()
        # Prevent huge visible "teleports" by limiting catch-up dropping.
        # (When we're behind, dropping is OK, but 100-frame bursts look like glitches.)
        max_drop_per_iter = int(min(15, max(5, video_fps // 2)))
        if DEBUG_MODE and FILE_REALTIME:
            print(f"[DEBUG] Real-time file playback enabled (target {video_fps:.2f} fps; will drop frames if behind)")
    while True:
        # Mark previous cycle models as waiting before next round
        _set_all_models_waiting()
        ret, frame = cap.read()
        if ret and is_video_file:
            frame_idx += 1
            CURRENT_FRAME_IDX = frame_idx
        if not ret:
            if is_video_file:
                # Looping logic for video file
                current_pos = cap.get(cv2.CAP_PROP_POS_FRAMES)
                total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                VIDEO_LOOP_COUNT += 1
                print(f"[INFO] Video reached end (frame {current_pos:.0f}/{total_frames:.0f}), looping... (loop #{VIDEO_LOOP_COUNT})")
                if DEBUG_MODE:
                    print(f"[DEBUG] Reached end of video at frame {current_pos}/{total_frames}, rewinding.")
                
                # Try simple rewind first
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()

                if ret:
                    # Reset per-loop counter to match fresh capture position.
                    frame_idx = 1
                    CURRENT_FRAME_IDX = frame_idx
                
                # If rewind fails, release and reopen the video file (more robust)
                if not ret:
                    if DEBUG_MODE:
                        print("[DEBUG] Simple rewind failed, reopening video file...")
                    cap.release()
                    cap, is_video_file = _open_video_capture(True, resolved_source)
                    if not cap or not cap.isOpened():
                        print("**ERROR: Cannot reopen video file. Exiting video loop.**")
                        break
                    ret, frame = cap.read()
                    if not ret:
                        print("**ERROR: Cannot read video file after reopen. Exiting video loop.**")
                        break
                    if DEBUG_MODE:
                        print("[DEBUG] Video file reopened successfully")

                    frame_idx = 1
                    CURRENT_FRAME_IDX = frame_idx
                
                # Reset real-time pacing baseline so elapsed math restarts
                if FILE_REALTIME:
                    playback_start = time.perf_counter()
                    # frame_idx already reset to 1 above when we successfully read after rewind.
                    if DEBUG_MODE:
                        print("[DEBUG] Real-time baseline reset after loop rewind")
            else:
                print("**CHECK CAMERA (no frames captured)**")
                break
        # For video file: drop frames to approximate real-time wall clock if enabled
        if is_video_file and FILE_REALTIME and playback_start and video_fps > 0:
            elapsed = time.perf_counter() - playback_start
            expected_count = int(elapsed * video_fps) + 1  # expected frames-read count (1-based)
            lag = expected_count - frame_idx

            # If we're ahead, sleep briefly to avoid racing the file.
            if lag < -2:
                target_elapsed = frame_idx / video_fps
                sleep_s = target_elapsed - elapsed
                if sleep_s > 0:
                    time.sleep(min(0.05, sleep_s))

            # If we're behind, fast-forward by reading & discarding a bounded number of frames.
            if lag > 2:  # allow small slack
                drop_target = min(lag - 1, max_drop_per_iter or 10)
                dropped = 0
                while dropped < drop_target:
                    ret2, frame2 = cap.read()
                    if not ret2:
                        # Hit end of video during frame skip - rewind and reset
                        VIDEO_LOOP_COUNT += 1
                        print(f"[INFO] Video reached end during frame skip, looping... (loop #{VIDEO_LOOP_COUNT})")
                        if DEBUG_MODE:
                            print(f"[DEBUG] Hit end of video during frame skip (dropped {dropped} frames), rewinding.")
                        
                        # Try simple rewind first
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        playback_start = time.perf_counter()
                        frame_idx = 0
                        
                        # Read the first frame after rewind to use for processing
                        ret_rewind, frame_rewind = cap.read()
                        
                        # If rewind fails, release and reopen the video file
                        if not ret_rewind:
                            if DEBUG_MODE:
                                print("[DEBUG] Simple rewind failed during skip, reopening video file...")
                            cap.release()
                            cap, is_video_file = _open_video_capture(True, resolved_source)
                            if cap and cap.isOpened():
                                ret_rewind, frame_rewind = cap.read()
                                if DEBUG_MODE and ret_rewind:
                                    print("[DEBUG] Video file reopened successfully during skip")
                        
                        if ret_rewind:
                            frame = frame_rewind  # Use first frame after rewind
                            frame_idx = 1  # frames-read count
                            CURRENT_FRAME_IDX = frame_idx
                            if DEBUG_MODE:
                                print(f"[DEBUG] Using first frame after rewind for processing")
                        else:
                            if DEBUG_MODE:
                                print(f"[DEBUG] Failed to read after rewind, keeping current frame")
                        break  # Exit drop loop and process the frame
                    # Update frame to the last successfully read frame during skip
                    frame = frame2
                    frame_idx += 1
                    CURRENT_FRAME_IDX = frame_idx
                    dropped += 1
                if DEBUG_MODE and dropped > 0:
                    print(f"[DEBUG] Dropped {dropped} frames to sync (elapsed={elapsed:.1f}s expected={expected_count} now={frame_idx} lag={expected_count - frame_idx})")
                # After fast-forward, use the last acquired 'frame' variable for processing (already read above)
        
        # Ensure we have a valid frame before processing
        if frame is None:
            print("**ERROR: Frame is None, cannot process. Exiting loop.**")
            break

        # Show a minimal window only if enabled
        if show_display:
            try:
                small_frame = cv2.resize(frame, (320, 240))
                cv2.imshow("Press 'q' to quit", small_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("Detected 'q' key press. Exiting...")
                    break
            except Exception as e:
                print(f"[WARN] Display error: {e}. Disabling further display.")
                show_display = False

        # State and Context
        doors_latched = False
        patient_present = False
        people_present = False
        pullup_found = False
        buildcab_found = False

        action_frame = frame

        # --- Action Recognition ---
        action_counter += 1
        scale = 1280 / max(frame.shape)
        if scale < 1:
            action_frame = cv2.resize(action_frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

        if action_counter > 50:
            (preprocessed, _) = preprocessing(action_frame, size)
            start_enc = time.time()
            encoder_output.append(encoder(preprocessed, compiled_encoder_model if INFERENCE_MODE=='local' else None))
            _record_model_inference('encoder', time.time() - start_enc)
            if len(encoder_output) == sample_duration:
                start_dec = time.time()
                decoded_labels, decoded_top_probs = decoder(encoder_output, compiled_decoder_model if INFERENCE_MODE=='local' else None)
                try:
                    globals()['LAST_ACTION_LABELS'] = [str(x) for x in decoded_labels[:3]]
                    globals()['LAST_ACTION_PROBS'] = [float(f"{p:.4f}") for p in decoded_top_probs[:3]]
                except Exception as _act_upd_err:
                    if DEBUG_MODE:
                        print(f"[DEBUG] action label update failed: {_act_upd_err}")
                _record_model_inference('decoder', time.time() - start_dec)
                encoder_output = []
                top_3_labels = decoded_labels[:3]
                pullup_found = "pull ups" in top_3_labels
                buildcab_found = "building cabinet" in top_3_labels
            elif PERFORMANCE_MODE:
                print(f"[PERF] Action recognition skipped: insufficient frames ({len(encoder_output)}/{sample_duration})")

        # --- Person Detection ---
        orig_h, orig_w = frame.shape[:2]
        input_w, input_h = 992, 800
        scale_x = orig_w / input_w
        scale_y = orig_h / input_h
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (input_w, input_h)).astype("float32")
        img = (img / 127.5) - 1.0
        input_tensor = img.transpose(2, 0, 1)[None]

        start_time = time.time()
        if INFERENCE_MODE == 'local':
            t0 = time.time()
            person_results = infer_with_retry(compiled_person_model, input_tensor, person_output, 'person')
            elapsed = time.time() - start_time
            _record_model_inference('person', time.time() - t0)
            if PERFORMANCE_MODE:
                print(f"[PERF] Inference: device=GPU, model={PERSON_MODEL_NAME}, mode=local, time={elapsed:.3f}s")
        else:
            result = ovms_infer(PERSON_MODEL_NAME, {"image": input_tensor})
            elapsed = time.time() - start_time
            # OVMS timing is printed inside ovms_infer
            person_results = list(result.values())[0] if result else np.zeros((1, 100, 5), dtype=np.float32)

        person_count = 0
        person_confidence_threshold = 0.3

        # --- rPPG Session Sampling (very naive placeholder using average green channel) ---
        if RPPG_SESSION_ACTIVE and RPPG_SESSION_START:
            try:
                # Crop center face-like region heuristic (middle 40%)
                h, w = frame.shape[:2]
                y0 = int(h*0.3); y1 = int(h*0.7)
                x0 = int(w*0.3); x1 = int(w*0.7)
                roi = frame[y0:y1, x0:x1]
                if roi.size > 0:
                    green_avg = float(np.mean(roi[:,:,1]))
                else:
                    green_avg = float(np.mean(frame[:,:,1]))
                ts_now = time.time()
                metrics = None  # ensure defined for outer scope check
                with RPPG_LOCK:
                    if RPPG_SESSION_ACTIVE:
                        RPPG_SIGNAL.append((ts_now, green_avg))
                        # Auto-stop if exceeds target duration
                        if (ts_now - RPPG_SESSION_START) >= RPPG_TARGET_DURATION:
                            # Copy before clearing
                            signal_copy = list(RPPG_SIGNAL)
                            session_start = RPPG_SESSION_START
                            try:
                                metrics = _compute_rppg_metrics(signal_copy, session_start)
                            except Exception as e:
                                if DEBUG_MODE:
                                    print(f"[DEBUG] rPPG auto-stop metrics computation failed: {e}")
                                metrics = None
                            RPPG_SESSION_ACTIVE = False
                            RPPG_SESSION_START = None
                            RPPG_SIGNAL = []
                    # Outside the lock: persist if we just stopped
                    if not RPPG_SESSION_ACTIVE and 'metrics' in locals() and metrics is not None:
                        try:
                            conn = sqlite3.connect("status.db")
                            c = conn.cursor()
                            c.execute("""INSERT INTO rppg_sessions (session_duration, heart_rate_avg, heart_rate_min, heart_rate_max, confidence_score, raw_signal, graph_data)
                                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                      (metrics['session_duration'], metrics['heart_rate_avg'], metrics['heart_rate_min'], metrics['heart_rate_max'], metrics['confidence_score'], json.dumps(metrics['raw_signal']), json.dumps(metrics['graph_data'])))
                            conn.commit()
                            sess_id = c.lastrowid
                            conn.close()
                            metrics['session_id'] = sess_id
                            metrics['started_at'] = session_start
                            if DEBUG_MODE:
                                print(f"[DEBUG] rPPG auto-stop saved session id={sess_id} hr_avg={metrics['heart_rate_avg']:.2f}")
                        except Exception as e:
                            if DEBUG_MODE:
                                print(f"[DEBUG] rPPG auto-stop save failed: {e}")
            except Exception as _rppg_err:
                if DEBUG_MODE:
                    print(f"[DEBUG] rPPG sample error: {_rppg_err}")
        person_boxes = []
        # Defensive: ensure person_results[0] is iterable
        detections = person_results[0]
        if DEBUG_MODE and DIAG_MODE and (frame_idx % LOG_EVERY == 0):
            print("[DIAG] person shape:", getattr(detections, 'shape', None), "sample:", str(detections)[:120])
        if not isinstance(detections, (list, tuple, np.ndarray)):
            print(f"Error: person_results[0] is not iterable: {detections}")
            detections = []
        if isinstance(detections, np.ndarray) and detections.ndim == 2 and detections.shape[1] == 5:
            for det in detections:
                x_min, y_min, x_max, y_max, conf = det
                if conf > person_confidence_threshold:
                    person_count += 1
                    pt1 = (int(x_min * scale_x), int(y_min * scale_y))
                    pt2 = (int(x_max * scale_x), int(y_max * scale_y))
                    person_boxes.append((pt1[0], pt1[1], pt2[0], pt2[1], conf))
        elif isinstance(detections, np.ndarray) and detections.ndim == 1:
            # Suppress warning for 1D outputs (e.g., shape (5,), (6,)), treat as no detections
            pass
        else:
            print(f"Warning: person_results[0] not in expected (N,5) format, got shape {getattr(detections, 'shape', None)}")
        person_boxes = filter_overlapping_boxes(person_boxes, iou_threshold=0.3)
        person_count = len(person_boxes)

        # --- Patient Detection ---
        input_tensor = (cv2.resize(frame, (input_w, input_h)).astype("float32") / 255.0).transpose(2, 0, 1)[None]
        start_time = time.time()
        if INFERENCE_MODE == 'local':
            t0 = time.time()
            patient_results = infer_with_retry(compiled_patient_model, input_tensor, patient_output, 'patient')
            elapsed = time.time() - start_time
            _record_model_inference('patient', time.time() - t0)
            if PERFORMANCE_MODE:
                print(f"[PERF] Inference: device=GPU, model={PATIENT_MODEL_NAME}, mode=local, time={elapsed:.3f}s")
        else:
            result = ovms_infer(PATIENT_MODEL_NAME, {"image": input_tensor})
            elapsed = time.time() - start_time
            # OVMS timing is printed inside ovms_infer
            patient_results = list(result.values())[0] if result else np.zeros((1, 100, 5), dtype=np.float32)

        patient_count = 0
        patient_confidence_threshold = .15
        patient_boxes = []
        # Defensive: ensure patient_results[0] is iterable
        detections = patient_results[0]
        if DEBUG_MODE and DIAG_MODE and (frame_idx % LOG_EVERY == 0):
            print("[DIAG] patient shape:", getattr(detections, 'shape', None), "sample:", str(detections)[:120])
        if not isinstance(detections, (list, tuple, np.ndarray)):
            print(f"Error: patient_results[0] is not iterable: {detections}")
            detections = []
        if isinstance(detections, np.ndarray) and detections.ndim == 2 and detections.shape[1] == 5:
            for det in detections:
                x_min, y_min, x_max, y_max, conf = det
                if conf > patient_confidence_threshold:
                    patient_present = True
                    patient_count += 1
                    pt1 = (int(x_min * scale_x), int(y_min * scale_y))
                    pt2 = (int(x_max * scale_x), int(y_max * scale_y))
                    patient_boxes.append((pt1[0], pt1[1], pt2[0], pt2[1], conf))
        elif isinstance(detections, np.ndarray) and detections.ndim == 1:
            # Suppress warning for 1D outputs (e.g., shape (3,)), treat as no detections
            pass
        else:
            print(f"Warning: patient_results[0] not in expected (N,5) format, got shape {getattr(detections, 'shape', None)}")
        patient_boxes = filter_overlapping_boxes(patient_boxes)
        patient_count = len(patient_boxes)

        if person_count > 0 and not patient_present:
            people_present = True
        elif patient_present and person_count == 1:
            people_present = False
        else:
            people_present = True if person_count > 1 else False

        # --- Latch Detection ---
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (input_w, input_h)).astype("float32")
        img = (img / 127.5) - 1.0
        input_tensor = img.transpose(2, 0, 1)[None]
        start_time = time.time()
        if INFERENCE_MODE == 'local':
            t0 = time.time()
            anomaly_results = infer_with_retry(compiled_latch_model, input_tensor, latch_output, 'latch')
            elapsed = time.time() - start_time
            _record_model_inference('latch', time.time() - t0)
            if PERFORMANCE_MODE:
                print(f"[PERF] Inference: device=GPU, model={LATCH_MODEL_NAME}, mode=local, time={elapsed:.3f}s")
        else:
            result = ovms_infer(LATCH_MODEL_NAME, {"image": input_tensor})
            elapsed = time.time() - start_time
            # OVMS timing is printed inside ovms_infer
            anomaly_results = list(result.values())[0] if result else np.zeros((1, 100, 5), dtype=np.float32)

        confidence_threshold = 0.3
        anomaly_boxes = []
        # Defensive: ensure anomaly_results[0] is iterable
        detections = anomaly_results[0]
        if DEBUG_MODE and DIAG_MODE and (frame_idx % LOG_EVERY == 0):
            print("[DIAG] latch shape:", getattr(detections, 'shape', None), "sample:", str(detections)[:120])
        if not isinstance(detections, (list, tuple, np.ndarray)):
            print(f"Error: anomaly_results[0] is not iterable: {detections}")
            detections = []
        if isinstance(detections, np.ndarray) and detections.ndim == 2 and detections.shape[1] == 5:
            for det in detections:
                x_min, y_min, x_max, y_max, conf = det
                if conf > confidence_threshold:
                    pt1 = (int(x_min * scale_x), int(y_min * scale_y))
                    pt2 = (int(x_max * scale_x), int(y_max * scale_y))
                    anomaly_boxes.append((pt1[0], pt1[1], pt2[0], pt2[1], conf))
        elif isinstance(detections, np.ndarray) and detections.ndim == 1:
            # Suppress warning for 1D outputs (e.g., shape (8,)), treat as no detections
            pass
        else:
            print(f"Warning: anomaly_results[0] not in expected (N,5) format, got shape {getattr(detections, 'shape', None)}")
        anomaly_boxes = filter_overlapping_boxes(anomaly_boxes)
        latch_count = len(anomaly_boxes)
        if latch_count >= 3:
            doors_latched = True

        # --- DB Updates ---
        if db_conn is None or db_cur is None:
            db_conn = sqlite3.connect("status.db")
            db_cur = db_conn.cursor()
            close_db_after = True
        else:
            close_db_after = False

        db_cur.execute("UPDATE status SET doors_latched = ?", ("true" if doors_latched else "false",))
        db_cur.execute("UPDATE status SET patient_present = ?", ("true" if patient_present else "false",))
        db_cur.execute("UPDATE status SET people_present = ?", ("true" if people_present else "false",))
        db_cur.execute("UPDATE workflow SET pullup_found = ?", ("true" if pullup_found else "false",))
        db_cur.execute("UPDATE workflow SET buildcab_found = ?", ("true" if buildcab_found else "false",))
        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        _set_latest_frame_bytes(frame_bytes)

        # --- Workflow progression (migrated from legacy update_dashboard) ---
        # Fetch current workflow row after updating found flags
        db_cur.execute("""
            SELECT pullup_found, buildcab_found, shared_window_start, both_latched_time,
                   pullup_latched, buildcab_latched
            FROM workflow
        """)
        wf_row = db_cur.fetchone()
        if wf_row:
            (wf_pullup_found, wf_buildcab_found, wf_shared_start,
             wf_both_time, wf_pullup_latched, wf_buildcab_latched) = wf_row

            now_dt = datetime.now()  # naive consistent with existing stored format
            changes = False

            # Normalize helpers
            def is_true(x): return x == 'true'
            def ts_present(x): return x not in (None, '0', '')

            # Start window when either action first detected
            if (is_true(wf_pullup_found) or is_true(wf_buildcab_found)) and not ts_present(wf_shared_start):
                new_start = now_dt.isoformat()
                db_cur.execute("UPDATE workflow SET shared_window_start = ?", (new_start,))
                wf_shared_start = new_start
                changes = True

            # Evaluate active window (5 minutes) if started
            in_window = False
            if ts_present(wf_shared_start):
                try:
                    start_dt = datetime.fromisoformat(wf_shared_start)
                    if now_dt - start_dt < timedelta(minutes=5):
                        in_window = True
                    else:
                        # Expired -> reset to baseline
                        db_cur.execute("""
                            UPDATE workflow SET shared_window_start='0', pullup_latched='false', buildcab_latched='false', both_latched_time='0'
                        """)
                        wf_shared_start = '0'
                        wf_pullup_latched = 'false'
                        wf_buildcab_latched = 'false'
                        wf_both_time = '0'
                        changes = True
                except Exception:
                    pass

            # Within window, latch transitions
            if in_window:
                if is_true(wf_pullup_found) and wf_pullup_latched != 'true':
                    db_cur.execute("UPDATE workflow SET pullup_latched='true'")
                    wf_pullup_latched = 'true'
                    changes = True
                if is_true(wf_buildcab_found) and wf_buildcab_latched != 'true':
                    db_cur.execute("UPDATE workflow SET buildcab_latched='true'")
                    wf_buildcab_latched = 'true'
                    changes = True
                if wf_pullup_latched == 'true' and wf_buildcab_latched == 'true' and not ts_present(wf_both_time):
                    both_ts = now_dt.isoformat()
                    db_cur.execute("UPDATE workflow SET both_latched_time = ?", (both_ts,))
                    wf_both_time = both_ts
                    changes = True

            if changes:
                # minimal commit already planned below; no extra action
                pass
        db_conn.commit()
        if close_db_after:
            db_conn.close()
            db_conn = None
            db_cur = None

        # frame_idx is advanced immediately on read/skip; no increment here.

    cap.release()
    if show_display:
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    if db_conn is not None:
        try:
            db_conn.close()
        except Exception:
            pass


# Start webcam processing in a background thread
def _process_frame_entry():
    try:
        print(f"[INFO] process_frame thread starting (source={'file:'+str(VIDEO_FILE) if VIDEO_FILE else 'camera:'+str(CAMERA_INDEX if CAMERA_INDEX is not None else 0)}) realtime={'on' if FILE_REALTIME else 'off'}")
        process_frame()
        print("[INFO] process_frame thread exited normally")
    except Exception as e:
        import traceback
        print("[ERROR] process_frame thread crashed:", e)
        traceback.print_exc()

if __name__ == "__main__" or getattr(sys, 'frozen', False):
    init_db()
    threading.Thread(target=_process_frame_entry, args=(), daemon=True).start()
    # Suppress default werkzeug request logging when not in debug mode
    if not DEBUG_MODE:
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        # Also silence Flask's own logger to errors only
        app.logger.setLevel(logging.ERROR)

# --- UI Diff Caches (to mitigate flicker) ---
last_box_html = [None, None, None, None]
last_rppg_heart_rate_html = None
last_rppg_confidence_html = None
last_rppg_timestamp_html = None
last_rppg_plot_html = None
last_frame_bytes_hash = None
last_image_paths = [None, None, None]

def update_dashboard():  
    """Periodic update callback providing only changed component values.
    Unchanged components return gr.update() to avoid re-render flashes.
    """
    global last_box_html, last_rppg_heart_rate_html, last_rppg_confidence_html, last_rppg_timestamp_html, last_rppg_plot_html
    global last_frame_bytes_hash, last_image_paths
    # Connect to the database
    conn = sqlite3.connect("status.db")
    c = conn.cursor()

    c.execute("SELECT doors_latched, patient_present, people_present FROM status")
    doors_latched, patient_present, people_present = c.fetchone()
    
    ####
    #print(doors_latched, patient_present, people_present)  

    # Determine image paths
    image1_path = "images/patient_present.jpg" if patient_present == "true" else "images/patient_absent.jpg"
    image2_path = "images/people_present.jpg" if people_present == "true" else "images/people_absent.jpg"
    image3_path = "images/doors_latched.jpg" if doors_latched == "true" else "images/doors_unlatched.jpg"

    # Fetch current state
    c.execute("""
        SELECT pullup_found, buildcab_found, shared_window_start, both_latched_time, 
            pullup_latched, buildcab_latched 
        FROM workflow
    """)
    pullup_found, buildcab_found, shared_start_ts, both_ts, pullup_latched, buildcab_latched = c.fetchone()

    now = datetime.now()

    # Parse timestamps
    shared_start_time = datetime.fromisoformat(shared_start_ts) if shared_start_ts != "0" else None
    both_latched_time = datetime.fromisoformat(both_ts) if both_ts != "0" else None

    # Initialize labels
    label_box0 = ""
    label_box3 = ""

    # Start shared window if needed
    if (pullup_found == "true" or buildcab_found == "true") and not shared_start_time:
        shared_start_time = now
        c.execute("UPDATE workflow SET shared_window_start = ?", (now.isoformat(),))
        conn.commit()

    # Determine if we're in the 5-minute window
    in_window = shared_start_time and now - shared_start_time < timedelta(minutes=5)

    # Latch detections during the window
    if in_window:
        label_box0 = f"<span class='label'>Window started at {shared_start_time.strftime('%H:%M:%S')}</span>"

        if pullup_found == "true" and pullup_latched != "true":
            c.execute("UPDATE workflow SET pullup_latched = 'true'")
            conn.commit()
            pullup_latched = "true"

        if buildcab_found == "true" and buildcab_latched != "true":
            c.execute("UPDATE workflow SET buildcab_latched = 'true'")
            conn.commit()
            buildcab_latched = "true"

        # If both latched, set box[3] green and record time
        if pullup_latched == "true" and buildcab_latched == "true":
            if not both_latched_time:
                both_latched_time = now
                c.execute("UPDATE workflow SET both_latched_time = ?", (now.isoformat(),))
                conn.commit()
            label_box3 = f"<span class='label'>Both latched at {both_latched_time.strftime('%H:%M:%S')}</span>"
            box4_color = "green"
        else:
            box4_color = "gray"
    else:
        # Reset everything after window expires
        if shared_start_time:
            c.execute("""
                UPDATE workflow 
                SET shared_window_start = '0', 
                    pullup_latched = 'false', 
                    buildcab_latched = 'false', 
                    both_latched_time = '0'
            """)
            conn.commit()
        shared_start_time = None
        pullup_latched = "false"
        buildcab_latched = "false"
        both_latched_time = None
        box4_color = "gray"

    # Final box colors using your format
    box_colors = [
        "gray",
        "purple" if pullup_latched == "true" and in_window else "gray",
        "purple" if buildcab_latched == "true" and in_window else "gray",
        box4_color
    ]

    # Final HTML output
    box_html = [
        f"<div class='box' style='background-color: {box_colors[0]};'>{label_box0}</div>",
        f"<div class='box' style='background-color: {box_colors[1]};'></div>",
        f"<div class='box' style='background-color: {box_colors[2]};'></div>",
        f"<div class='box' style='background-color: {box_colors[3]};'>{label_box3}</div>",
    ]

    ### Handle frame updates
    c.execute("SELECT latest_frame FROM frames")
    frame_data = c.fetchone()[0]
    if frame_data and frame_data != b'None':
        nparr = np.frombuffer(frame_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    else:
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.putText(frame, "No Frame", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    ### Fetch rPPG data
    try:
        c.execute("""SELECT * FROM rppg_sessions 
                     ORDER BY timestamp DESC LIMIT 1""")
        rppg_row = c.fetchone()
        
        if rppg_row:
            # Parse rPPG data
            rppg_id, rppg_timestamp_str, session_duration, heart_rate_avg, heart_rate_min, heart_rate_max, confidence_score, raw_signal_json, graph_data_json = rppg_row
            
            # Format heart rate display
            rppg_heart_rate_html = f"""<div class='rppg-metric'>
                <h3 style='color: #e74c3c; margin: 0;'>Heart Rate</h3>
                <p style='font-size: 24px; margin: 5px 0; font-weight: bold;'>{heart_rate_avg:.1f} BPM</p>
                <small>Range: {heart_rate_min:.1f} - {heart_rate_max:.1f}</small>
            </div>"""
            
            # Format confidence display
            confidence_percent = confidence_score * 100 if confidence_score else 0
            confidence_color = "#27ae60" if confidence_percent > 70 else "#f39c12" if confidence_percent > 40 else "#e74c3c"
            rppg_confidence_html = f"""<div class='rppg-metric'>
                <h3 style='color: {confidence_color}; margin: 0;'>Signal Quality</h3>
                <p style='font-size: 20px; margin: 5px 0; font-weight: bold;'>{confidence_percent:.0f}%</p>
                <small>Session: {session_duration}s</small>
            </div>"""
            
            # Format timestamp display
            # Display the session time adjusted to local system timezone.
            # Assumption: stored timestamp is UTC if naive (no tzinfo). If it already has tzinfo, convert to local.
            try:
                session_dt = datetime.fromisoformat(rppg_timestamp_str)
                if session_dt.tzinfo is None:
                    # Assume UTC for naive timestamp
                    session_dt = session_dt.replace(tzinfo=timezone.utc)
                local_dt = session_dt.astimezone()  # convert to local system timezone
                time_str = local_dt.strftime("%H:%M:%S")
                date_str = local_dt.strftime("%m/%d")
                tooltip_str = local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
            except Exception:
                time_str = "Unknown"
                date_str = ""
                tooltip_str = rppg_timestamp_str or "Unknown"

            rppg_timestamp_html = f"""<div class='rppg-metric' title='Session time {tooltip_str}'>
                <h3 style='color: #3498db; margin: 0;'>Last Updated</h3>
                <p style='font-size: 18px; margin: 5px 0; font-weight: bold;'>{time_str}</p>
                <small>{date_str}</small>
            </div>"""
            
            # Create simple pulse waveform visualization
            try:
                raw_signal = json.loads(raw_signal_json) if raw_signal_json else []
                if len(raw_signal) > 0:
                    # Take every 10th point for display
                    display_points = raw_signal[::max(1, len(raw_signal)//50)]
                    # Normalize to 0-100 range for display
                    if len(display_points) > 1:
                        min_val, max_val = min(display_points), max(display_points)
                        if max_val != min_val:
                            normalized = [(x - min_val) / (max_val - min_val) * 100 for x in display_points]
                            
                            # Create simple SVG pulse display
                            svg_points = " ".join([f"{i},{100-val}" for i, val in enumerate(normalized)])
                            width_units = len(normalized)
                            rppg_plot_html = f"""<div class='rppg-plot'>
                                <h4 style='margin: 0 0 10px 0;'>Pulse Waveform</h4>
                                <div class='rppg-svg-wrapper'>
                                    <svg class='rppg-svg' viewBox='0 0 {width_units} 100' preserveAspectRatio='none' style='border:1px solid #ddd; background:#f9f9f9;'>
                                        <polyline points='{svg_points}' style='fill:none;stroke:#e74c3c;stroke-width:0.5' />
                                    </svg>
                                </div>
                                <p style='font-size: 12px; margin: 5px 0;'>Last {len(raw_signal)} samples</p>
                            </div>"""
                        else:
                            rppg_plot_html = "<div class='rppg-plot'><p>Signal data available but flat</p></div>"
                    else:
                        rppg_plot_html = "<div class='rppg-plot'><p>Insufficient signal data</p></div>"
                else:
                    rppg_plot_html = "<div class='rppg-plot'><p>No signal data available</p></div>"
            except Exception as plot_error:
                rppg_plot_html = f"<div class='rppg-plot'><p>Error processing signal: {str(plot_error)}</p></div>"
                
        else:
            # No rPPG data available
            rppg_heart_rate_html = "<div class='rppg-metric'><h3>Heart Rate</h3><p>No data</p></div>"
            rppg_confidence_html = "<div class='rppg-metric'><h3>Signal Quality</h3><p>No data</p></div>"
            rppg_timestamp_html = "<div class='rppg-metric'><h3>Last Updated</h3><p>No sessions</p></div>"
            rppg_plot_html = "<div class='rppg-plot'><p>Complete an rPPG session to see pulse data</p></div>"
            
    except Exception as rppg_error:
        # If rPPG processing fails, provide error message but don't break the dashboard
        print(f"rPPG processing error: {rppg_error}")
        rppg_heart_rate_html = "<div class='rppg-metric'><h3>Heart Rate</h3><p>Error loading</p></div>"
        rppg_confidence_html = "<div class='rppg-metric'><h3>Signal Quality</h3><p>Error loading</p></div>"
        rppg_timestamp_html = "<div class='rppg-metric'><h3>Last Updated</h3><p>Error loading</p></div>"
        rppg_plot_html = "<div class='rppg-plot'><p>Error loading rPPG data</p></div>"

    conn.close()

    # Differential updates
    import gradio as gr  # local import to avoid circular during module load

    # Images
    image_updates = []
    for i, p in enumerate([image1_path, image2_path, image3_path]):
        if last_image_paths[i] != p:
            last_image_paths[i] = p
            image_updates.append(p)
        else:
            image_updates.append(gr.update())

    # Boxes
    box_updates = []
    for i in range(4):
        if last_box_html[i] != box_html[i]:
            last_box_html[i] = box_html[i]
            box_updates.append(box_html[i])
        else:
            box_updates.append(gr.update())

    # Frame
    if frame is not None:
        frame_hash = hash(frame.tobytes())
    else:
        frame_hash = None
    if frame_hash != last_frame_bytes_hash:
        last_frame_bytes_hash = frame_hash
        frame_out = frame
    else:
        frame_out = gr.update()

    # rPPG metrics
    if rppg_heart_rate_html != last_rppg_heart_rate_html:
        last_rppg_heart_rate_html = rppg_heart_rate_html
        hr_out = rppg_heart_rate_html
    else:
        hr_out = gr.update()

    if rppg_confidence_html != last_rppg_confidence_html:
        last_rppg_confidence_html = rppg_confidence_html
        conf_out = rppg_confidence_html
    else:
        conf_out = gr.update()

    if rppg_timestamp_html != last_rppg_timestamp_html:
        last_rppg_timestamp_html = rppg_timestamp_html
        ts_out = rppg_timestamp_html
    else:
        ts_out = gr.update()

    if rppg_plot_html != last_rppg_plot_html:
        last_rppg_plot_html = rppg_plot_html
        plot_out = rppg_plot_html
    else:
        plot_out = gr.update()

    return [*image_updates, *box_updates, frame_out, hr_out, conf_out, ts_out, plot_out]

custom_css = """
#top-bar {
    padding: 20px 0 20px 20px;
    width: 75%;
    margin: auto;
}
#box-bar {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 50px;
    margin-top: 20px;
}
.box {
    width: 100px;
    height: 100px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: bold;
    border: 1px solid #ccc;
    margin: 5px;
}
.label {
    font-size: 12px;
    text-align: center;
}
.rppg-metric {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 15px;
    margin: 5px;
    text-align: center;
    min-height: 80px;
}
.rppg-plot {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 15px;
    margin: 5px;
    text-align: center;
    min-height: 140px;
    width: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.rppg-plot .rppg-svg-wrapper {
    width: 100%;
    overflow: hidden;
}
.rppg-plot .rppg-svg {
    width: 100%;
    height: 120px;
    display: block;
}
"""

def run_flask_only():
    # Provide a concise startup message (we already printed one above for video thread)
    if not DEBUG_MODE:
        print("[INFO] Flask server running (request logs suppressed). Set --debug to re-enable verbose output.")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    # Start frame processing thread
    t = threading.Thread(target=process_frame, daemon=True)
    t.start()
    print("API server starting on http://localhost:5000 (Gradio removed; use Next.js frontend).")
    run_flask_only()