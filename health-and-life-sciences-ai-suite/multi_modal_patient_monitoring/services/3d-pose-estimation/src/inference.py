"""
Pose Inference Engine
Handles model loading and inference for 3D pose estimation
"""

import cv2
import numpy as np
from openvino import Core

from engine3js import parse_poses


class PoseInference:
    """Handles 3D pose estimation inference using OpenVINO"""

    def __init__(self, model_path: str, device: str = "CPU"):
        """
        Initialize pose inference engine
        
        Args:
            model_path: Path to OpenVINO IR model XML file
            device: Inference device (CPU, GPU, etc.)
        """
        print(f"[INFO] Initializing PoseInference on device: {device}")
        
        # Initialize OpenVINO
        self.core = Core()
        self.model = self.core.read_model(model_path)
        self.compiled_model = self.core.compile_model(self.model, device)
        
        # Get input/output info
        self.input_layer = self.compiled_model.input(0)
        self.input_shape = self.input_layer.shape
        
        # Model configuration
        self.target_size = (self.input_shape[3], self.input_shape[2])  # (width, height)
        self.stride = 8
        
        print(f"[INFO] Model loaded successfully")
        print(f"[INFO] Input shape: {self.input_shape}")
        print(f"[INFO] Target size: {self.target_size}")

    def preprocess(self, frame):
        """
        Preprocess frame for inference (matching standalone code)
        
        Args:
            frame: Input frame (BGR)
            
        Returns:
            Preprocessed tensor and resized frame
        """
        target_w, target_h = self.target_size
        
        # Resize to target size
        resized = cv2.resize(frame, (target_w, target_h))
        
        # Crop to stride boundaries
        h_crop = resized.shape[0] - (resized.shape[0] % self.stride)
        w_crop = resized.shape[1] - (resized.shape[1] % self.stride)
        cropped = resized[:h_crop, :w_crop]
        
        # Normalize: (pixel - 128) / 255
        normalized = (cropped.astype(np.float32) - 128.0) / 255.0
        
        # Convert to CHW format and add batch dimension
        input_tensor = np.transpose(normalized, (2, 0, 1))[None, ...]
        
        return input_tensor, resized

    def extract_poses(self, heatmaps, pafs, features, resized_frame):
        """
        Extract 2D and 3D poses from model outputs
        
        Args:
            heatmaps: Heatmap outputs from model
            pafs: Part Affinity Fields from model
            features: 3D coordinate features from model
            resized_frame: The resized frame for focal length calculation
            
        Returns:
            poses_3d: List of 3D poses
            poses_2d: List of 2D poses
        """
        # Calculate focal length based on frame width
        focal_length = 0.8 * resized_frame.shape[1]
        
        # Call parse_poses from engine3js
        # Input format: (heatmaps, pafs, features) - all without batch dimension
        poses_3d, poses_2d = parse_poses(
            inference_results=(heatmaps, pafs, features),
            input_scale=1.0,  # We already resized to target size
            stride=self.stride,
            fx=focal_length,
            is_video=True
        )
        
        return poses_3d, poses_2d

    def process_frame(self, frame):
        """
        Process a single frame
        
        Args:
            frame: Input frame (BGR)
            
        Returns:
            annotated_frame: Frame with 2D skeleton overlay
            poses_3d: List of 3D poses
            poses_2d: List of 2D poses
        """
        # Preprocess
        input_tensor, resized_frame = self.preprocess(frame)
        
        # Run inference
        result = self.compiled_model(input_tensor)
        
        # Extract outputs (matching standalone: heatmaps, pafs, features)
        # Model outputs 3 tensors with batch dimension
        heatmaps = result[0][0]  # Remove batch dimension
        pafs = result[1][0]      # Remove batch dimension
        features = result[2][0]  # Remove batch dimension
        
        # Extract poses
        poses_3d, poses_2d = self.extract_poses(heatmaps, pafs, features, resized_frame)
        
        # Draw 2D skeleton on frame
        annotated_frame = self.draw_poses(frame, poses_2d, resized_frame)
        
        return annotated_frame, poses_3d, poses_2d

    def draw_poses(self, frame, poses_2d, resized_frame):
        """
        Draw 2D skeleton on frame (matching standalone code)
        
        Args:
            frame: Original input frame
            poses_2d: List of 2D poses
            resized_frame: The resized frame used for inference
            
        Returns:
            Annotated frame
        """
        annotated = frame.copy()
        
        # Skeleton connections (matching standalone)
        skeleton_connections = np.array([
            [0, 1], [1, 16], [16, 18],  # neck-nose, nose-left eye-ear
            [1, 15], [15, 17],           # nose-right eye-ear
            [0, 3], [3, 4], [4, 5],      # neck-left arm
            [0, 9], [9, 10], [10, 11],   # neck-right arm
            [0, 6], [6, 7], [7, 8],      # neck-left leg
            [0, 12], [12, 13], [13, 14], # neck-right leg
        ])
        
        for pose_data in poses_2d:
            if len(pose_data) == 0:
                continue
            
            # Reshape keypoints: [x0, y0, conf0, x1, y1, conf1, ..., score]
            keypoints = np.array(pose_data[:-1]).reshape((-1, 3)).T  # Shape: (3, num_joints)
            confidence = keypoints[2] > 0
            
            # Scale keypoints to original frame size
            keypoints[0] = keypoints[0] * frame.shape[1] / resized_frame.shape[1]
            keypoints[1] = keypoints[1] * frame.shape[0] / resized_frame.shape[0]
            
            # Draw limb connections
            for connection in skeleton_connections:
                pt1_idx, pt2_idx = connection
                if pt1_idx < keypoints.shape[1] and pt2_idx < keypoints.shape[1]:
                    if confidence[pt1_idx] and confidence[pt2_idx]:
                        pt1 = tuple(keypoints[:2, pt1_idx].astype(np.int32))
                        pt2 = tuple(keypoints[:2, pt2_idx].astype(np.int32))
                        cv2.line(annotated, pt1, pt2, (0, 255, 255), 3, cv2.LINE_AA)
            
            # Draw joint circles
            for joint_idx in range(keypoints.shape[1]):
                if confidence[joint_idx]:
                    center = tuple(keypoints[:2, joint_idx].astype(np.int32))
                    cv2.circle(annotated, center, 4, (255, 0, 255), -1, cv2.LINE_AA)
        
        return annotated