"""
3D Pose Estimation Service
Main orchestrator for pose estimation inference and gRPC publishing
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


class PoseEstimationService:
    """Main service orchestrator"""

    def __init__(self, model_path: str, aggregator_address: str, source_id: str = "camera-1", 
                 device: str = "CPU"):
        """
        Initialize the service
        
        Args:
            model_path: Path to OpenVINO IR model
            aggregator_address: Address of aggregator gRPC server
            source_id: Identifier for this video source
            device: OpenVINO device (CPU, GPU, etc.)
        """
        print("[INFO] Initializing Pose Estimation Service")
        
        # Initialize components
        self.inference = PoseInference(model_path, device)
        self.encoder = PoseEncoder(source_id)
        self.publisher = GrpcPosePublisher(aggregator_address, source_id)
        
        # Performance tracking
        self.frame_count = 0
        self.fps_tracker = deque(maxlen=30)
        
        print("[INFO] Service initialized successfully")

    def filter_valid_poses(self, poses_2d, poses_3d):
        """
        Filter poses to keep only high-quality detections
        
        Args:
            poses_2d: List of 2D poses
            poses_3d: List of 3D poses
            
        Returns:
            Filtered poses_2d and poses_3d lists
        """
        filtered_2d = []
        filtered_3d = []
        
        for i, pose_2d in enumerate(poses_2d):
            if len(pose_2d) == 0:
                continue
            
            # Parse keypoints from pose_2d
            # Format: [x0, y0, conf0, x1, y1, conf1, ..., overall_score]
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
                filtered_3d.append(poses_3d[i])
        
        return filtered_2d, filtered_3d

    def process_video(self, video_source, flip: bool = False, max_frames: int = None):
        """
        Main processing loop
        
        Args:
            video_source: Path to video file or webcam index (0)
            flip: Flip video horizontally (for webcams)
            max_frames: Maximum frames to process (None for unlimited)
        """
        cap = cv2.VideoCapture(video_source)

        if not cap.isOpened():
            print(f"[ERROR] Cannot open video source: {video_source}")
            return

        print(f"[INFO] Processing video from: {video_source}")
        print(f"[INFO] Waiting for start command...")

        # Wait for start command
        while not is_processing_enabled():
            time.sleep(1)

        print(f"[INFO] Processing enabled! Starting pose estimation...")
        print(f"[INFO] Press Ctrl+C to stop")

        try:
            while True:
                # Check if processing is still enabled
                if not is_processing_enabled():
                    print("[INFO] Processing paused, waiting for resume...")
                    while not is_processing_enabled():
                        time.sleep(1)
                    print("[INFO] Processing resumed")

                ret, frame = cap.read()
                if not ret:
                    print("[INFO] Video stream ended")
                    break

                if flip:
                    frame = cv2.flip(frame, 1)

                self.frame_count += 1

                # Process frame
                start_time = time.perf_counter()
                
                annotated_frame, poses_3d, poses_2d = self.inference.process_frame(frame)
                
                inference_time = time.perf_counter() - start_time
                self.fps_tracker.append(inference_time)

                # Filter poses
                filtered_poses_2d, filtered_poses_3d = self.filter_valid_poses(poses_2d, poses_3d)

                # Log filtering results
                if self.frame_count % 30 == 0:
                    print(f"[DEBUG] Frame {self.frame_count}: "
                          f"Raw detections={len(poses_3d)}, "
                          f"After filtering={len(filtered_poses_3d)}")

                # Encode data with filtered poses
                data_packet = self.encoder.encode_data(
                    annotated_frame,
                    filtered_poses_3d,
                    filtered_poses_2d,
                    frame_number=self.frame_count
                )

                # Publish to aggregator via gRPC
                success = self.publisher.publish(data_packet)

                # Calculate metrics
                avg_time_ms = np.mean(self.fps_tracker) * 1000
                current_fps = 1000 / avg_time_ms if avg_time_ms > 0 else 0

                # Log progress every 30 frames
                if self.frame_count % 30 == 0:
                    person_count = len(filtered_poses_3d)
                    if person_count > 0:
                        print(f"[INFO] Frame {self.frame_count}: "
                              f"{avg_time_ms:.1f}ms | {current_fps:.1f} FPS | "
                              f"Persons: {person_count} | "
                              f"Published: {'✓' if success else '✗'}")
                    else:
                        print(f"[INFO] Frame {self.frame_count}: "
                              f"{avg_time_ms:.1f}ms | {current_fps:.1f} FPS | "
                              f"No persons detected | "
                              f"Published: {'✓' if success else '✗'}")

                # Check max frames limit
                if max_frames and self.frame_count >= max_frames:
                    print(f"[INFO] Reached max frames limit: {max_frames}")
                    break

        except KeyboardInterrupt:
            print("\n[INFO] Interrupted by user")

        finally:
            # Cleanup
            cap.release()
            self.publisher.close()
            print(f"\n[INFO] Processed {self.frame_count} frames")
            self.publisher.print_stats()


def main():
    # Start control server in background thread
    control_thread = threading.Thread(target=start_control_server, daemon=True)
    control_thread.start()
    control_port = os.getenv("CONTROL_PORT", "8083")
    print(f"[INFO] Control server started on port {control_port}")
    
    parser = argparse.ArgumentParser(description="3D Pose Estimation Service")
    parser.add_argument("--model", required=True, help="Path to OpenVINO IR model XML")
    parser.add_argument("--video", default="0", help="Video file path or webcam index (default: 0)")
    parser.add_argument("--aggregator", default="localhost:50051", help="Aggregator gRPC address")
    parser.add_argument("--source-id", default="3d-pose-camera-1", help="Source identifier")
    parser.add_argument("--device", default="CPU", help="OpenVINO device (CPU, GPU, MYRIAD, etc.)")
    parser.add_argument("--flip", action="store_true", help="Flip video horizontally (for webcams)")
    parser.add_argument("--max-frames", type=int, help="Maximum frames to process")

    args = parser.parse_args()

    # Initialize service
    service = PoseEstimationService(
        model_path=args.model,
        aggregator_address=args.aggregator,
        source_id=args.source_id,
        device=args.device
    )

    # Parse video source - handle both file paths and webcam indices
    video_source = args.video
    if isinstance(video_source, str) and video_source.isdigit():
        video_source = int(video_source)
    
    # Process video
    service.process_video(
        video_source=video_source,
        flip=args.flip,
        max_frames=args.max_frames
    )


if __name__ == "__main__":
    main()