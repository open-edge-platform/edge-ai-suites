# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import tempfile
from faster_whisper import WhisperModel
import time
import json
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__, static_folder="static")
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB — matches nginx client_max_body_size

MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")
print(f"Loading Whisper model: {MODEL_SIZE} ...")
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
print("Model loaded.")

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

# Video (audio) length in seconds
video_length_last = Gauge(
    "stt_video_length_seconds_last",
    "Duration of the last submitted audio/video file in seconds"
)
video_length_total = Counter(
    "stt_video_length_seconds_total",
    "Cumulative duration of all submitted audio/video files in seconds"
)

# Processing time in seconds
processing_time_last = Gauge(
    "stt_processing_time_seconds_last",
    "Transcription processing time for the last request in seconds"
)
processing_time_total = Counter(
    "stt_processing_time_seconds_total",
    "Cumulative transcription processing time across all requests in seconds"
)

# Real-time factor: video_length / processing_time  (>1 means faster than real-time)
rtf_last = Gauge(
    "stt_realtime_factor_last",
    "Real-time factor for the last request (audio duration / processing time). "
    ">1 means faster than real-time."
)
rtf_sum = Gauge(
    "stt_realtime_factor_sum",
    "Real-time factor computed from cumulative totals "
    "(total audio duration / total processing time)."
)

# Plain Python accumulators for cumulative RTF — avoids accessing private
# prometheus_client internals (_value.get()).
_total_audio_seconds: float = 0.0
_total_proc_seconds: float = 0.0

def record_metrics(audio_duration_seconds: float, processing_time_seconds: float) -> None:
    """Update all Prometheus metrics after a completed transcription."""
    global _total_audio_seconds, _total_proc_seconds

    video_length_last.set(audio_duration_seconds)
    video_length_total.inc(audio_duration_seconds)

    processing_time_last.set(processing_time_seconds)
    processing_time_total.inc(processing_time_seconds)

    if processing_time_seconds > 0:
        rtf_last.set(audio_duration_seconds / processing_time_seconds)

    # Cumulative RTF using plain accumulators
    _total_audio_seconds += audio_duration_seconds
    _total_proc_seconds += processing_time_seconds
    if _total_proc_seconds > 0:
        rtf_sum.set(_total_audio_seconds / _total_proc_seconds)


def transcribe_audio_chunks(audio_path, chunk_duration=10):
    """
    Transcribe audio and yield results as segments arrive.
    faster-whisper returns a segment generator — no manual chunking needed.
    """
    all_segments = []
    detected_language = "unknown"

    try:
        segments_gen, info = model.transcribe(
            audio_path,
            language=None,
            task="transcribe",
            beam_size=5,
        )
        detected_language = info.language
        total_duration = info.duration or 1.0

        for segment in segments_gen:
            seg_dict = {
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
            }
            all_segments.append(seg_dict)
            progress = min(100, int((segment.end / total_duration) * 100))

            yield json.dumps({
                "type": "chunk",
                "progress": progress,
                "duration": round(segment.end, 2),
                "segments": [seg_dict],
            }) + "\n"

        yield json.dumps({
            "type": "complete",
            "text": " ".join(s["text"] for s in all_segments).strip(),
            "language": detected_language,
            "all_segments": all_segments,
        }) + "\n"
    finally:
        try:
            os.unlink(audio_path)
        except FileNotFoundError:
            pass


@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/transcribe", methods=["POST"])
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    suffix = ".webm"
    if audio_file.filename:
        ext = os.path.splitext(audio_file.filename)[1]
        if ext:
            suffix = ext

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        start_time = time.time()

        # Check if streaming is requested
        if request.args.get("stream") == "true":
            def generate():
                audio_duration = 0.0
                for chunk_data in transcribe_audio_chunks(tmp_path):
                    # Track total audio duration from the last chunk/complete event
                    try:
                        parsed = json.loads(chunk_data)
                        if "duration" in parsed:
                            audio_duration = parsed["duration"]
                    except Exception:
                        pass
                    yield chunk_data
                # Record metrics after streaming completes
                processing_time = time.time() - start_time
                record_metrics(audio_duration, processing_time)
            # File cleanup is handled inside transcribe_audio_chunks
            return Response(generate(), mimetype="application/x-ndjson")
        else:
            # Original behavior: process entire file at once with timing
            try:
                segments_gen, info = model.transcribe(tmp_path, task="transcribe")
                processing_time = time.time() - start_time

                segments = [
                    {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
                    for s in segments_gen
                ]
                audio_duration = round(segments[-1]["end"], 3) if segments else 0.0
                record_metrics(audio_duration, processing_time)

                return jsonify({
                    "text": " ".join(s["text"] for s in segments).strip(),
                    "language": info.language,
                    "processing_time_seconds": round(processing_time, 2),
                    "segments": segments,
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500
            finally:
                os.unlink(tmp_path)
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"status": "ok", "model": MODEL_SIZE})

@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
