import cv2
import pandas as pd
import paho.mqtt.client as mqtt
import time
import base64
import subprocess
import json
import os

AVI_PATH = "/simulation-data/welding_good.avi"
CSV_PATH = "/simulation-data/welding_good.csv"

MQTT_BROKER = os.getenv("MQTT_BROKER", "ia-mqtt-broker")
MEDIAMTX_SERVER = os.getenv("MEDIAMTX_SERVER", "mediamtx")
MEDIAMTX_PORT = os.getenv("MEDIAMTX_PORT", "8554")
RTSP_STREAM_NAME = os.getenv("RTSP_STREAM_NAME", "live.stream")
VIDEO_TOPIC = os.getenv("VIDEO_TOPIC", "weld/video")
DATA_TOPIC = os.getenv("DATA_TOPIC", "ts_welding_data")
RTSP_URL = f"rtsp://{MEDIAMTX_SERVER}:{MEDIAMTX_PORT}/{RTSP_STREAM_NAME}"

published_data = []

def stream_video_and_csv():
    # Read CSV
    df = pd.read_csv(CSV_PATH)
    num_rows = len(df)
    frame_id = 0

    # Open video
    cap = cv2.VideoCapture(AVI_PATH)
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
    client = mqtt.Client()
    client.connect(MQTT_BROKER)

    
    start_ffmpeg = False

    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            cap = cv2.VideoCapture(AVI_PATH)
            frame_count = 0
            global published_data
            published_data = []
            continue
        
        # Start ffmpeg process on first frame
        if not start_ffmpeg:
            start_ffmpeg = True
            ffmpeg_cmd = [
            "ffmpeg",
            "-re",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{frame.shape[1]}x{frame.shape[0]}",
            "-r", str(int(fps)),
            "-i", "-",  # Read from stdin
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-f", "rtsp",
            RTSP_URL
            ]
            ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
        # Calculate which CSV row this frame belongs to
            
        current_time = frame_count / fps if fps > 0 else 0
        row_idx = int(current_time / row_time_window) if row_time_window > 0 else 0
        print(f"Current time: {current_time:.2f} seconds, Row index: {row_idx}")
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
    client.disconnect()

if __name__ == "__main__":
    stream_video_and_csv()
