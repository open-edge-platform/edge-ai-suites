#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import cv2
import pandas as pd
import paho.mqtt.client as mqtt
import time
import base64
import subprocess
import json
import os
import glob
from typing import Tuple, Optional
import logging

MQTT_BROKER = os.getenv("MQTT_BROKER", "ia-mqtt-broker")
MEDIAMTX_SERVER = os.getenv("MEDIAMTX_SERVER", "mediamtx")
MEDIAMTX_PORT = os.getenv("MEDIAMTX_PORT", "8554")
RTSP_STREAM_NAME = os.getenv("RTSP_STREAM_NAME", "live.stream")
TS_TOPIC = os.getenv("TS_TOPIC", "weld-data")
RTSP_URL = f"rtsp://{MEDIAMTX_SERVER}:{MEDIAMTX_PORT}/{RTSP_STREAM_NAME}"
ffmpeg_proc = None
client = None

FRAME_RATE = 30  # Frames per second for video streaming
FRAME_WIDTH = 960
FRAME_HEIGHT = 600
published_data = []

# Configure logging

log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging_level = getattr(logging, log_level, logging.INFO)

# Configure logging
logging.basicConfig(
    level=logging_level,  # Set the log level to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log format
)
logger = logging.getLogger(__name__)

def read_simulation_files(base_filename: str, simulation_data_dir: str = "/simulation-data") -> Tuple[Optional[str], Optional[str]]:
    """
    Read paired simulation files (video and CSV) with the same base name.
    
    Args:
        base_filename: Base name of the files (without extension)
        simulation_data_dir: Directory containing simulation data files
        
    Returns:
        Tuple of (video_path, csv_path) if both files exist, otherwise (None, None)
    """
    video_path = os.path.join(simulation_data_dir, f"{base_filename}.avi")
    csv_path = os.path.join(simulation_data_dir, f"{base_filename}.csv")
    
    # Check if both files exist
    if os.path.exists(video_path) and os.path.exists(csv_path):
        logger.info(f"Found paired files:")
        logger.info(f"  Video: {video_path}")
        logger.info(f"  CSV: {csv_path}")
        return video_path, csv_path
    else:
        logger.info(f"Could not find both files for base name '{base_filename}'")
        if not os.path.exists(video_path):
            logger.info(f"  Missing video file: {video_path}")
        if not os.path.exists(csv_path):
            logger.info(f"  Missing CSV file: {csv_path}")
        return None, None


def get_available_simulation_files(simulation_data_dir: str = "/simulation-data") -> list:
    """
    Get list of available simulation file pairs.
    
    Args:
        simulation_data_dir: Directory containing simulation data files
        
    Returns:
        List of base filenames that have both video and CSV files
    """
    # Find all .avi files
    video_files = glob.glob(os.path.join(simulation_data_dir, "*.avi"))
    available_pairs = []
    
    for video_file in video_files:
        base_name = os.path.splitext(os.path.basename(video_file))[0]
        csv_file = os.path.join(simulation_data_dir, f"{base_name}.csv")
        
        if os.path.exists(csv_file):
            available_pairs.append(base_name)
    
    return available_pairs


def load_simulation_data(base_filename: str, simulation_data_dir: str = "/simulation-data") -> Tuple[Optional[cv2.VideoCapture], Optional[pd.DataFrame]]:
    """
    Load both video and CSV data for a given base filename.
    
    Args:
        base_filename: Base name of the files (without extension)
        simulation_data_dir: Directory containing simulation data files
        
    Returns:
        Tuple of (video_capture, dataframe) if successful, otherwise (None, None)
    """
    video_path, csv_path = read_simulation_files(base_filename, simulation_data_dir)
    
    if video_path is None or csv_path is None:
        return None, None
    
    try:
        # Load video
        video_cap = cv2.VideoCapture(video_path)
        if not video_cap.isOpened():
            logger.error(f"Error: Could not open video file {video_path}")
            return None, None
        
        # Load CSV
        df = pd.read_csv(csv_path)
        logger.debug(f"Successfully loaded:")
        logger.info(f"  Video frames: {int(video_cap.get(cv2.CAP_PROP_FRAME_COUNT))} CSV rows: {len(df)}")        
        return video_cap, df
        
    except Exception as e:
        logger.error(f"Error loading simulation data: {e}")
        return None, None




def stream_video_and_csv(base_filename: str, simulation_data_dir: str = "/simulation-data", target_fps: float = None):
    """
    Stream video and CSV data via MQTT and RTSP.
    
    Args:
        base_filename: Base name of the files to stream (without extension).
                      If None, uses default hardcoded paths.
        simulation_data_dir: Directory containing simulation data files
        target_fps: Target FPS for streaming. If None, uses original video FPS.
                   If provided, will downsample the video to this FPS rate.
    """
    if base_filename:
        
        # Use the new function to load paired files
        cap, df = load_simulation_data(base_filename, simulation_data_dir)
        if cap is None or df is None:
            logger.error(f"Failed to load simulation data for '{base_filename}'")
            return
    else:
        logger.error("No base filename provided, skipping streaming.")
        return
        
    num_rows = len(df)
    frame_id = 0

    # Open video (if not already opened by load_simulation_data)
    if not cap.isOpened():
        logger.error("Error: Could not open video file")
        return
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    original_fps = fps
    
    # Apply FPS downframing if specified
    if target_fps is not None and target_fps > 0:
        if target_fps > fps:
            logger.fatal(f"Warning: Target FPS ({target_fps}) is higher than original FPS ({fps}). Using original FPS.")
            effective_fps = fps
        else:
            effective_fps = target_fps
            logger.info(f"Downframing from {fps:.2f} FPS to {effective_fps:.2f} FPS")
    else:
        effective_fps = fps
    
    # Calculate frame skip ratio for downframing
    frame_skip_ratio = int(fps / effective_fps) if effective_fps < fps else 1
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps if fps > 0 else 0

    logger.info(f"Video duration: {duration_sec:.2f} seconds")
    logger.info(f"Original FPS: {original_fps:.2f}")
    logger.info(f"Effective FPS: {effective_fps:.2f}")
    logger.info(f"Total frames: {total_frames}")
    if frame_skip_ratio > 1:
        logger.info(f"Frame skip ratio: {frame_skip_ratio} (showing every {frame_skip_ratio} frames)")

    # Correlate each CSV row to a time window in the video
    # Each row covers duration_sec / num_rows seconds
    row_time_window = duration_sec / num_rows if num_rows > 0 else 0
    logger.info(f"Row time window: {row_time_window:.2f} seconds")
    # MQTT setup
    global client
    client = mqtt.Client()
    client.connect(MQTT_BROKER)

    start_ffmpeg = False
    global ffmpeg_proc

    frame_count = 0
    processed_frame_count = 0  # Count of frames actually processed/streamed
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            # Reset video to beginning for looping
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            frame_count = 0
            processed_frame_count = 0
            global published_data
            published_data = []
            return
            
        # Skip frames for downframing
        if frame_count % frame_skip_ratio != 0:
            frame_count += 1
            continue
            
        # Calculate which CSV row this frame belongs to (based on original timing)
        current_time = frame_count / original_fps if original_fps > 0 else 0
        row_idx = int(current_time / row_time_window) if row_time_window > 0 else 0
        logger.info(f"Frame {frame_count}, Time: {current_time:.2f}s, Row: {row_idx}, Processed: {processed_frame_count} for '{base_filename}'")
        
        if row_idx >= num_rows:
            row_idx = num_rows - 1
        csv_row = df.iloc[row_idx].to_dict()

        # Publish to MQTT
        # Stream frame bytes as RTSP video using ffmpeg subprocess
        # This requires ffmpeg to be installed and accessible

        # Write frame bytes to ffmpeg stdin
        ffmpeg_proc.stdin.write(frame.tobytes())
        
        if "Date" in csv_row:
            del csv_row["Date"]
        if "Time" in csv_row:
            del csv_row["Time"]
        if "Remarks " in csv_row:   
            del csv_row["Remarks "]
        if "Part No " in csv_row:   
            del csv_row["Part No"]
        # csv_row["frame_id"] = frame_id
        csv_row = json.dumps(csv_row)
        # Publish each CSV row only once
        
        # global published_data
        
        client.publish(TS_TOPIC, str(csv_row))
        frame_id += 1
        frame_count += 1
        processed_frame_count += 1
        time.sleep(1 / effective_fps)  # Use effective FPS for timing
        
    cap.release()


def check_and_load_simulation_files(target_fps):
    """
    Display the available simulation file pairs and provide usage examples.
    """
    available_files = get_available_simulation_files()
    if available_files:
        logger.info("simulation file pairs found!")
    else:
        logger.info("No simulation file pairs found!")
        return

    continuous_ingestion = os.getenv("CONTINUOUS_SIMULATOR_INGESTION", "true").lower() == "true"
    
    while True:
        for i, filename in enumerate(available_files, 1):
            logger.info(f"  {i}. {filename}")
            stream_video_and_csv(filename, target_fps=target_fps)
        if not continuous_ingestion:
            break
    
    


if __name__ == "__main__":
    # Uncomment the line below to see available files
    # demo_available_files()
    
    # Example of using specific simulation files with FPS downframing:
    # stream_video_and_csv("good_weld_02-16-23-0081-00")  # Original FPS
    # stream_video_and_csv("good_weld_02-16-23-0081-00", target_fps=10)  # Downsample to 10 FPS
    # stream_video_and_csv("crater_cracks_03-20-23-0122-11", target_fps=5)  # Downsample to 5 FPS
    
    # Default behavior - process all available files
    client = mqtt.Client()
    client.connect(MQTT_BROKER)
    target_fps = int(os.getenv("SIMULATION_TARGET_FPS", "10"))
    ffmpeg_cmd = [
    "ffmpeg",
    "-re",
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-s", f"{FRAME_WIDTH}x{FRAME_HEIGHT}",
    "-r", str(target_fps),
    "-i", "-",  # Read from stdin
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-f", "rtsp",
    RTSP_URL
    ]

    ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
    check_and_load_simulation_files(target_fps)

    if 'ffmpeg_proc' in locals():
        ffmpeg_proc.stdin.close()
        ffmpeg_proc.wait()
    client.disconnect()
