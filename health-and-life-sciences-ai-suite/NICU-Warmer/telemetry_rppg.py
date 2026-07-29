"""Telemetry and rPPG helper utilities separated from dashboard.py for clarity."""
from collections import deque
import time
import numpy as np
import threading

# Model performance telemetry
MODEL_STATS = {}
_MODEL_STATS_LOCK = threading.Lock()

def _ensure_model_entry(name: str):
    if name not in MODEL_STATS:
        MODEL_STATS[name] = {
            'frames': 0,
            'fps_ema': 0.0,
            'fps_min': None,
            'fps_max': None,
            'last_time': None,
            'status': 'waiting',
            'latency_samples': deque(maxlen=200),
            'lat_avg': None,
            'lat_med': None,
            'lat_min': None,
            'lat_max': None,
            'lat_hist': [0,0,0,0,0]
        }

def record_model_inference(name: str, latency: float):
    with _MODEL_STATS_LOCK:
        _ensure_model_entry(name)
        ms = MODEL_STATS[name]
        now = time.time()
        ms['frames'] += 1
        if ms['last_time'] is not None:
            fps = 1.0 / max(1e-6, now - ms['last_time'])
            alpha = 0.2
            ms['fps_ema'] = fps if ms['fps_ema'] == 0 else (alpha*fps + (1-alpha)*ms['fps_ema'])
            ms['fps_min'] = fps if (ms['fps_min'] is None or fps < ms['fps_min']) else ms['fps_min']
            ms['fps_max'] = fps if (ms['fps_max'] is None or fps > ms['fps_max']) else ms['fps_max']
        ms['last_time'] = now
        ms['status'] = 'running'
        ms['latency_samples'].append(latency)
        ls = list(ms['latency_samples'])
        if ls:
            ms['lat_avg'] = float(np.mean(ls))
            ms['lat_med'] = float(np.median(ls))
            ms['lat_min'] = float(np.min(ls))
            ms['lat_max'] = float(np.max(ls))
            buckets = [0,0,0,0,0]
            for v in ls:
                ms_val = v*1000.0
                if ms_val < 10: buckets[0]+=1
                elif ms_val < 30: buckets[1]+=1
                elif ms_val < 60: buckets[2]+=1
                elif ms_val < 120: buckets[3]+=1
                else: buckets[4]+=1
            ms['lat_hist'] = buckets

def set_all_models_waiting():
    with _MODEL_STATS_LOCK:
        for ms in MODEL_STATS.values():
            if ms['status'] == 'running':
                ms['status'] = 'waiting'

def model_stats_snapshot():
    with _MODEL_STATS_LOCK:
        snap = {}
        for k,v in MODEL_STATS.items():
            snap[k] = {
                'frames': v['frames'],
                'fps': v['fps_ema'],
                'fps_min': v['fps_min'],
                'fps_max': v['fps_max'],
                'status': v['status'],
                'lat_avg': v['lat_avg'],
                'lat_med': v['lat_med'],
                'lat_min': v['lat_min'],
                'lat_max': v['lat_max'],
                'lat_hist': v['lat_hist']
            }
        return snap

# rPPG metrics computation
RPPG_TARGET_DURATION = 30  # seconds auto-stop

def compute_rppg_metrics(rppg_signal, session_start):
    if not rppg_signal or session_start is None:
        return None
    ts_vals, raw_vals = zip(*rppg_signal)
    raw_signal = list(raw_vals)
    session_duration = int(ts_vals[-1] - ts_vals[0]) if len(ts_vals) > 1 else 0
    try:
        sig = np.array(raw_signal)
        sig = sig - np.mean(sig)
        n = len(sig)
        if n < 10:
            return None
        freqs = np.fft.rfftfreq(n, d=1/30.0)
        fft_mag = np.abs(np.fft.rfft(sig))
        mask = (freqs*60 >= 40) & (freqs*60 <= 180)
        if not np.any(mask):
            return None
        peak_idx = np.argmax(fft_mag[mask])
        hr_candidates = freqs[mask]*60
        heart_rate = float(hr_candidates[peak_idx])
        heart_rate_min = float(np.min(hr_candidates))
        heart_rate_max = float(np.max(hr_candidates))
        confidence = float(fft_mag[mask][peak_idx] / (np.sum(fft_mag[mask]) + 1e-6))
    except Exception:
        heart_rate = heart_rate_min = heart_rate_max = confidence = 0.0
    return {
        'session_duration': session_duration,
        'heart_rate_avg': heart_rate,
        'heart_rate_min': heart_rate_min,
        'heart_rate_max': heart_rate_max,
        'confidence_score': confidence,
        'raw_signal': raw_signal,
        'graph_data': []
    }
