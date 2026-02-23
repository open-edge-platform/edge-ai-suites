import subprocess
import signal
import sys
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)
_recorders: Dict[str, subprocess.Popen] = {}

def start_rtsp_recording(
    name: str,
    rtsp_url: str,
    output_file: str,
) -> bool:
    """
    Start recording an RTSP stream using FFmpeg.
    Returns True if started, False if already running.
    """

    if name in _recorders and _recorders[name].poll() is None:
        logger.warning(f"Recorder '{name}' already running")
        return False

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-i", rtsp_url,
        "-c", "copy",
        "-movflags", "+faststart",
        "-y",
        str(output_path),
    ]

    logger.info(f"Starting RTSP recorder '{name}'")
    logger.info(" ".join(cmd))

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP
            if sys.platform == "win32"
            else 0
        ),
    )

    _recorders[name] = process
    return True


def stop_rtsp_recording(name: str, timeout: float = 10.0) -> bool:
    """
    Stop a running RTSP recorder gracefully.
    """

    process = _recorders.get(name)
    if not process:
        logger.warning(f"Recorder '{name}' not found")
        return False

    if process.poll() is not None:
        del _recorders[name]
        return True

    logger.info(f"Stopping RTSP recorder '{name}'")

    try:
        if sys.platform == "win32":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()

        process.wait(timeout=timeout)

    except subprocess.TimeoutExpired:
        logger.warning("Recorder did not stop gracefully, killing")
        process.kill()
        process.wait(timeout=5)

    del _recorders[name]
    return True

def is_rtsp_recording_running(name: str) -> bool:
    process = _recorders.get(name)
    return process is not None and process.poll() is None
