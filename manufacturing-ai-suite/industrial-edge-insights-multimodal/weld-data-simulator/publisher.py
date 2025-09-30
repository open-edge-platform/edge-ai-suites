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

AVI_PATH = "/simulation-data/welding_good.avi"
CSV_PATH = "/simulation-data/welding_good.csv"

MQTT_BROKER = os.getenv("MQTT_BROKER", "ia-mqtt-broker")
MEDIAMTX_SERVER = os.getenv("MEDIAMTX_SERVER", "mediamtx")
MEDIAMTX_PORT = os.getenv("MEDIAMTX_PORT", "8554")
RTSP_STREAM_NAME = os.getenv("RTSP_STREAM_NAME", "live.stream")
VIDEO_TOPIC = os.getenv("VIDEO_TOPIC", "weld/video")
DATA_TOPIC = os.getenv("DATA_TOPIC", "weld-data")
RTSP_URL = f"rtsp://{MEDIAMTX_SERVER}:{MEDIAMTX_PORT}/{RTSP_STREAM_NAME}"
ffmpeg_proc = None
client = None

FRAME_RATE = 30  # Frames per second for video streaming
FRAME_WIDTH = 960
FRAME_HEIGHT = 600
published_data = []


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
        print(f"Found paired files:")
        print(f"  Video: {video_path}")
        print(f"  CSV: {csv_path}")
        return video_path, csv_path
    else:
        print(f"Could not find both files for base name '{base_filename}'")
        if not os.path.exists(video_path):
            print(f"  Missing video file: {video_path}")
        if not os.path.exists(csv_path):
            print(f"  Missing CSV file: {csv_path}")
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
            print(f"Error: Could not open video file {video_path}")
            return None, None
        
        # Load CSV
        df = pd.read_csv(csv_path)
        print(f"Successfully loaded:")
        print(f"  Video frames: {int(video_cap.get(cv2.CAP_PROP_FRAME_COUNT))}")
        print(f"  CSV rows: {len(df)}")
        
        return video_cap, df
        
    except Exception as e:
        print(f"Error loading simulation data: {e}")
        return None, None




def stream_video_and_csv(base_filename: str, simulation_data_dir: str = "/simulation-data"):
    """
    Stream video and CSV data via MQTT and RTSP.
    
    Args:
        base_filename: Base name of the files to stream (without extension).
                      If None, uses default hardcoded paths.
        simulation_data_dir: Directory containing simulation data files
    """
    if base_filename:
        
        # Use the new function to load paired files
        cap, df = load_simulation_data(base_filename, simulation_data_dir)
        if cap is None or df is None:
            print(f"Failed to load simulation data for '{base_filename}'")
            return
    else:
        print("No base filename provided, skipping streaming.")
        return
        
    num_rows = len(df)
    frame_id = 0

    # Open video (if not already opened by load_simulation_data)
    if not cap.isOpened():
        print("Error: Could not open video file")
        return
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps if fps > 0 else 0

    print(f"Video duration: {duration_sec:.2f} seconds")
    print(f"Video FPS: {fps:.2f}")
    print(f"Total frames: {total_frames}")

    # Correlate each CSV row to a time window in the video
    # Each row covers duration_sec / num_rows seconds
    row_time_window = duration_sec / num_rows if num_rows > 0 else 0
    print(f"Row time window: {row_time_window:.2f} seconds")
    # MQTT setup
    global client
    

    
    start_ffmpeg = False

    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            # Reset video to beginning for looping
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            frame_count = 0
            global published_data
            published_data = []
            return
            # continue
        
        global ffmpeg_proc
            
        # Calculate which CSV row this frame belongs to
            
        current_time = frame_count / fps if fps > 0 else 0
        row_idx = int(current_time / row_time_window) if row_time_window > 0 else 0
        print(f"Current time: {current_time:.2f} seconds, Row index: {row_idx} for base '{base_filename}'")
        
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
        
        client.publish(DATA_TOPIC, str(csv_row))
        frame_id += 1
        frame_count += 1
        time.sleep(1 / fps)  # Simulate real-time streaming
        # time.sleep(1)  # Simulate real-time streaming
    cap.release()
    # client.disconnect()


def check_and_load_files():
    """
    Check and load the available simulation files.
    """
    print("Available simulation file pairs:")
    available_files = get_available_simulation_files()

    continuous_ingestion = os.getenv("CONTINUOUS_SIMULATOR_INGESTION", "true").lower() == "true"
    while True:
        for i, filename in enumerate(available_files, 1):
            print(f"  {i}. {filename}")
            stream_video_and_csv(filename)
        if not continuous_ingestion:
            break
    for i, filename in enumerate(available_files, 1):
        print(f"  {i}. {filename}")
        stream_video_and_csv(available_files[i])

    if not available_files:
        print("No simulation file pairs found!")


if __name__ == "__main__":
    # Uncomment the line below to see available files
    # global ffmpeg_proc
    # global client

    client = mqtt.Client()
    client.connect(MQTT_BROKER)

    start_ffmpeg = True
    ffmpeg_cmd = [
    "ffmpeg",
    "-re",
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-s", f"{FRAME_WIDTH}x{FRAME_HEIGHT}",
    "-r", str(FRAME_RATE),
    "-i", "-",  # Read from stdin
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-f", "rtsp",
    RTSP_URL
    ]
    
    ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
    check_and_load_files()
    
