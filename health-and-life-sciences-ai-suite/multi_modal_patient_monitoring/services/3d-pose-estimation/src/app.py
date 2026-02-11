"""
<<<<<<< HEAD
3D Pose Estimation Service
Main orchestrator for pose estimation inference and gRPC publishing
=======
3D Pose Estimation Service with MJPEG Streaming
Main orchestrator for pose estimation inference, MJPEG streaming, and gRPC publishing
>>>>>>> dev
"""

import sys
import time
import cv2
import numpy as np
from collections import deque
from pathlib import Path
import argparse
import threading
import os

# Import our modules
from inference import PoseInference
from pose_encoder import PoseEncoder
from publisher import GrpcPosePublisher
from controller_start_stop import start_control_server, is_processing_enabled
<<<<<<< HEAD


class PoseEstimationService:
    """Main service orchestrator"""

    def __init__(self, model_path: str, aggregator_address: str, source_id: str = "camera-1"):
=======
from mjpeg_streamer import MJPEGStreamer


class PoseEstimationService:
    """Main service orchestrator with MJPEG streaming"""

    def __init__(self, model_path: str, aggregator_address: str, source_id: str = "camera-1",
                 mjpeg_port: int = 8085, mjpeg_quality: int = 80):
>>>>>>> dev
        """
        Initialize the service
        
        Args:
            model_path: Path to OpenVINO IR model
            aggregator_address: Address of aggregator gRPC server
            source_id: Identifier for this video source
<<<<<<< HEAD
        """
        print("[INFO] Initializing Pose Estimation Service")
=======
            mjpeg_port: Port for MJPEG streaming
            mjpeg_quality: JPEG quality for streaming (1-100)
        """
        print("[INFO] Initializing Pose Estimation Service with MJPEG Streaming")
>>>>>>> dev
        
        self.target_fps = 20
        self.frame_interval = 1.0 / self.target_fps  
        
        # Device selection is handled by inference.py using POSE_3D_DEVICE env var
        print(f"[INFO] Using OpenVINO device from environment: {os.getenv('POSE_3D_DEVICE', 'GPU')}")
        print(f"[INFO] Target output FPS: {self.target_fps} (frame interval: {self.frame_interval:.3f}s)")
<<<<<<< HEAD
        
        # Initialize components - inference.py handles device selection internally
        self.inference = PoseInference(model_path)
        self.encoder = PoseEncoder(source_id)
        self.publisher = GrpcPosePublisher(aggregator_address, source_id)
        
=======
        print(f"[INFO] MJPEG streaming on port: {mjpeg_port}")
        
        # Initialize components
        self.inference = PoseInference(model_path)
        self.encoder = PoseEncoder(source_id)  # No frame encoding needed
        self.publisher = GrpcPosePublisher(aggregator_address, source_id)
        
        # Initialize MJPEG streamer
        self.mjpeg_streamer = MJPEGStreamer(port=mjpeg_port, quality=mjpeg_quality)
        self.mjpeg_streamer.start_server()
        
>>>>>>> dev
        # Performance tracking
        self.frame_count = 0
        self.fps_tracker = deque(maxlen=30)
        
        print("[INFO] Service initialized successfully")
<<<<<<< HEAD

    def filter_valid_poses(self, poses_2d, poses_3d):
        """
        Filter poses to keep only high-quality detections
        
        Args:
            poses_2d: List of 2D poses
            poses_3d: List of 3D poses
            
        Returns:
            Filtered poses_2d and poses_3d lists
        """
=======
        print(f"[INFO] MJPEG stream available at: http://localhost:{mjpeg_port}/video_feed")

    def filter_valid_poses(self, poses_2d, poses_3d):
        """Filter poses to keep only high-quality detections"""
>>>>>>> dev
        filtered_2d = []
        filtered_3d = []
        
        for i, pose_2d in enumerate(poses_2d):
            if len(pose_2d) == 0:
                continue
            
            # Parse keypoints from pose_2d
<<<<<<< HEAD
            # Format: [x0, y0, conf0, x1, y1, conf1, ..., overall_score]
=======
>>>>>>> dev
            num_joints = (len(pose_2d) - 1) // 3
            
            # Count valid keypoints (high confidence)
            valid_keypoints = 0
            for j in range(num_joints):
                conf = pose_2d[j * 3 + 2]  # Confidence for keypoint j
                if conf > 0.2:  # Confidence threshold
                    valid_keypoints += 1
            
            # Get overall pose score
            overall_score = pose_2d[-1] if len(pose_2d) > 0 else 0
            
            # Accept pose if:
            # 1. Has at least 8 valid keypoints (out of 19)
            # 2. Overall score > 0.4
            if valid_keypoints >= 8 and overall_score > 0.4:
                filtered_2d.append(pose_2d)
                if i < len(poses_3d):
                    filtered_3d.append(poses_3d[i])
        
        return filtered_2d, filtered_3d

    def process_video(self, video_source, flip: bool = False, max_frames: int = None):
        """
<<<<<<< HEAD
        Main processing loop - keeps service alive and restartable
=======
        Main processing loop with MJPEG streaming
>>>>>>> dev
        
        Args:
            video_source: Path to video file or webcam index (0)
            flip: Flip video horizontally (for webcams)
            max_frames: Maximum frames to process (None for unlimited)
        """
        print(f"[INFO] Video source: {video_source}")
        print(f"[INFO] Service ready - waiting for commands...")
    
        try:
<<<<<<< HEAD
            # Main service loop - never exits, waits for start/stop commands
=======
            # Main service loop
>>>>>>> dev
            while True:
                # Wait for start command
                print(f"[INFO] Waiting for start command...")
                while not is_processing_enabled():
                    time.sleep(0.5)
    
                print(f"[INFO] Processing enabled! Starting pose estimation at {self.target_fps} FPS...")
                
                # Reset frame count and timing for new session
                session_frame_count = 0
<<<<<<< HEAD
                last_frame_time = 0  # ✅ Initialize frame timing control
=======
                last_frame_time = 0
>>>>>>> dev
                session_start_time = time.time()
                
                # Processing loop - continues until stop command
                while is_processing_enabled():
                    # Open video source (fresh connection each time)
                    cap = cv2.VideoCapture(video_source)
    
                    if not cap.isOpened():
                        print(f"[ERROR] Cannot open video source: {video_source}")
                        time.sleep(2)
                        continue
    
                    # Get video properties
                    fps = int(cap.get(cv2.CAP_PROP_FPS))
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    
                    is_webcam = isinstance(video_source, int) or video_source == '0'
                    
                    if not is_webcam:
                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        print(f"[INFO] Video: {width}x{height} @ {fps}fps, {total_frames} frames")
                    else:
                        print(f"[INFO] Webcam: {width}x{height} @ {fps}fps")
    
                    # Process frames from this video iteration
                    while is_processing_enabled():
<<<<<<< HEAD
                        # ✅ Frame rate control: Check if enough time has passed
=======
                        # Frame rate control: Check if enough time has passed
>>>>>>> dev
                        current_time = time.time()
                        if last_frame_time > 0 and (current_time - last_frame_time) < self.frame_interval:
                            # Sleep for remaining time to maintain target FPS
                            sleep_time = self.frame_interval - (current_time - last_frame_time)
                            if sleep_time > 0:
                                time.sleep(sleep_time)
                                continue
                        
                        ret, frame = cap.read()
                        
                        if not ret:
                            if is_webcam:
                                print("[WARNING] Failed to read from webcam")
                                break
                            else:
                                print(f"[INFO] Video ended at frame {session_frame_count}. Restarting...")
                                break
    
                        if flip:
                            frame = cv2.flip(frame, 1)
    
                        self.frame_count += 1
                        session_frame_count += 1
                        
<<<<<<< HEAD
                        # ✅ Update frame timing after successful capture
=======
                        # Update frame timing after successful capture
>>>>>>> dev
                        last_frame_time = current_time
    
                        # Process frame
                        start_time = time.perf_counter()
                        
                        annotated_frame, poses_3d, poses_2d = self.inference.process_frame(frame)
                        
                        inference_time = time.perf_counter() - start_time
                        self.fps_tracker.append(inference_time)
    
                        # Filter poses
                        filtered_poses_2d, filtered_poses_3d = self.filter_valid_poses(poses_2d, poses_3d)
    
<<<<<<< HEAD
                        # Encode data with filtered poses
                        data_packet = self.encoder.encode_data(
                            annotated_frame,
=======
                        # ✅ Stream annotated frame via MJPEG
                        self.mjpeg_streamer.update_frame(annotated_frame)
    
                        # ✅ Encode pose data only (no frame data)
                        data_packet = self.encoder.encode_data(
>>>>>>> dev
                            filtered_poses_3d,
                            filtered_poses_2d,
                            frame_number=self.frame_count
                        )
    
<<<<<<< HEAD
                        # Publish to aggregator via gRPC
                        success = self.publisher.publish(data_packet)
    
                        # ✅ Calculate actual output FPS based on frame timing
=======
                        # Publish pose data to aggregator via gRPC
                        success = self.publisher.publish(data_packet)
    
                        # Calculate actual output FPS based on frame timing
>>>>>>> dev
                        session_duration = current_time - session_start_time
                        actual_output_fps = session_frame_count / session_duration if session_duration > 0 else 0
                        
                        # Calculate inference performance
                        avg_inference_ms = np.mean(self.fps_tracker) * 1000
                        inference_fps = 1000 / avg_inference_ms if avg_inference_ms > 0 else 0
    
<<<<<<< HEAD
                        # Log progress every 60 frames (every 3 seconds at 20 FPS)
=======
                        # Log progress every 40 frames (every 2 seconds at 20 FPS)
>>>>>>> dev
                        if session_frame_count % 40 == 0:
                            person_count = len(filtered_poses_3d)
                            status_msg = f"✓ {person_count} persons" if person_count > 0 else "No persons detected"
                            print(f"[INFO] Session frame {session_frame_count}: "
                                  f"Inference: {avg_inference_ms:.1f}ms ({inference_fps:.1f} FPS) | "
                                  f"Output: {actual_output_fps:.1f} FPS | "
<<<<<<< HEAD
                                  f"{status_msg} | Published: {'✓' if success else '✗'}")
=======
                                  f"{status_msg} | Streaming: ✓ | Published: {'✓' if success else '✗'}")
>>>>>>> dev
    
                        # Check max frames limit (optional)
                        if max_frames and session_frame_count >= max_frames:
                            print(f"[INFO] Reached max frames limit: {max_frames}")
                            cap.release()
                            return
    
                    # Release video capture for this iteration
                    cap.release()
                    
                    # Small delay before restarting video (only for video files)
                    if not is_webcam and is_processing_enabled():
                        time.sleep(0.5)
    
                # Processing stopped - cleanup and wait for next start
                print(f"[INFO] Processing stopped after {session_frame_count} frames")
                print(f"[INFO] Service remains active, waiting for next start command...")
    
        except KeyboardInterrupt:
            print("\n[INFO] Service interrupted by user")
            return
    
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
<<<<<<< HEAD
            # Don't exit - stay alive for restart
=======
>>>>>>> dev
            print("[INFO] Service will continue running...")
            time.sleep(1)
    
        finally:
            # Cleanup
            try:
                cap.release()
            except:
                pass
            
<<<<<<< HEAD
=======
            self.mjpeg_streamer.stop_server()
>>>>>>> dev
            print(f"[INFO] Total frames processed in this session: {self.frame_count}")


def main():
    # Start control server in background thread
    control_thread = threading.Thread(target=start_control_server, daemon=True)
    control_thread.start()
    control_port = os.getenv("CONTROL_PORT", "8083")
    print(f"[INFO] Control server started on port {control_port}")
    
<<<<<<< HEAD
    parser = argparse.ArgumentParser(description="3D Pose Estimation Service")
=======
    parser = argparse.ArgumentParser(description="3D Pose Estimation Service with MJPEG Streaming")
>>>>>>> dev
    parser.add_argument("--model", required=True, help="Path to OpenVINO IR model XML")
    parser.add_argument("--video", default="0", help="Video file path or webcam index (default: 0)")
    parser.add_argument("--aggregator", default="localhost:50051", help="Aggregator gRPC address")
    parser.add_argument("--source-id", default="3d-pose-camera-1", help="Source identifier")
    parser.add_argument("--flip", action="store_true", help="Flip video horizontally (for webcams)")
    parser.add_argument("--max-frames", type=int, help="Maximum frames to process")
<<<<<<< HEAD

    args = parser.parse_args()

    # Initialize service (device selection handled by environment variables)
    service = PoseEstimationService(
        model_path=args.model,
        aggregator_address=args.aggregator,
        source_id=args.source_id
    )

    # Parse video source - handle both file paths and webcam indices
=======
    parser.add_argument("--mjpeg-port", type=int, default=8085, help="MJPEG streaming port")
    parser.add_argument("--mjpeg-quality", type=int, default=80, help="MJPEG quality (1-100)")

    args = parser.parse_args()

    # Initialize service with MJPEG streaming
    service = PoseEstimationService(
        model_path=args.model,
        aggregator_address=args.aggregator,
        source_id=args.source_id,
        mjpeg_port=args.mjpeg_port,
        mjpeg_quality=args.mjpeg_quality
    )

    # Parse video source
>>>>>>> dev
    video_source = args.video
    if isinstance(video_source, str) and video_source.isdigit():
        video_source = int(video_source)
    
<<<<<<< HEAD
    # Process video
=======
    # Process video with streaming
>>>>>>> dev
    service.process_video(
        video_source=video_source,
        flip=args.flip,
        max_frames=args.max_frames
    )


if __name__ == "__main__":
    main()