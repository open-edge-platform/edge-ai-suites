import os
import subprocess
from uuid import uuid4
import atexit
import shutil
from utils.config_loader import config
import logging

logger = logging.getLogger(__name__)

CHUNK_DURATION =  config.audio_preprocessing.chunk_duration_sec # seconds
SILENCE_THRESH = config.audio_preprocessing.silence_threshold  # in dB
SILENCE_DURATION = config.audio_preprocessing.silence_duration # in seconds
SEARCH_WINDOW = config.audio_preprocessing.search_window_sec
CLEAN_UP_ON_EXIT = config.app.cleanup_on_exit

CHUNKS_DIR = config.audio_preprocessing.chunk_output_path
os.makedirs(CHUNKS_DIR, exist_ok=True)

@atexit.register
def cleanup_chunks_folder():
    if os.path.exists(CHUNKS_DIR) and CLEAN_UP_ON_EXIT:
        shutil.rmtree(CHUNKS_DIR)
        logger.info(f"Cleaned up {CHUNKS_DIR} directory on exit.")

def get_audio_duration(audio_path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", audio_path
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")

    return float(result.stdout.strip())

def detect_silences(audio_path):
    result = subprocess.run([
        "ffmpeg", "-i", audio_path, "-af",
        f"silencedetect=noise={SILENCE_THRESH}dB:d={SILENCE_DURATION}",
        "-f", "null", "-"
    ], stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")

    output = result.stderr
    silences = []

    current_silence = {}
    for line in output.split('\n'):
        if "silence_start" in line:
            current_silence['start'] = float(line.split("silence_start:")[1])
        elif "silence_end" in line:
            current_silence['end'] = float(line.split("silence_end:")[1].split('|')[0])
            silences.append(current_silence)
            current_silence = {}
    return silences

def get_closest_silence(silences, target_time, window=SEARCH_WINDOW):
    closest = None
    closest_diff = float('inf')

    for silence in silences:
        # Check if target time is within the silence interval
        if silence['start'] <= target_time <= silence['end']:
            return target_time

        # Check distance to start and end points
        for key in ['start', 'end']:
            diff = abs(silence[key] - target_time)
            if diff <= window and diff < closest_diff:
                closest = silence[key]
                closest_diff = diff

    return closest  # None if nothing close enough

def chunk_audio_by_silence(audio_path):

    if SEARCH_WINDOW > CHUNK_DURATION:
        raise ValueError(f"Silence search window ({SEARCH_WINDOW}s) can't be more then Chunk Duration({CHUNK_DURATION}s).")

    duration = get_audio_duration(audio_path)
    silences = detect_silences(audio_path)

    current_time = 0.0
    chunk_index = 0

    while current_time < duration:
        ideal_end = current_time + CHUNK_DURATION
        end_time = get_closest_silence(silences, ideal_end)

        cut_by_silence = True
        if not end_time or end_time <= current_time or end_time > duration:
            end_time = min(ideal_end, duration)
            cut_by_silence = False

        chunk_name = f"chunk_{chunk_index}_{uuid4().hex[:6]}.wav"
        chunk_path = os.path.join(CHUNKS_DIR, chunk_name)

        subprocess.run([
            "ffmpeg", "-y", "-i", audio_path,
            "-ss", str(current_time), "-to", str(end_time),
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", "-vn",
            chunk_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, encoding="utf-8", errors="replace")

        chunk_meta = {
            "chunk_path": chunk_path,
            "start_time": current_time,
            "end_time": end_time if end_time < duration else None,
            "chunk_index": chunk_index,
            "cut_by_silence": cut_by_silence
        }

        yield chunk_meta

        current_time = end_time
        chunk_index += 1
