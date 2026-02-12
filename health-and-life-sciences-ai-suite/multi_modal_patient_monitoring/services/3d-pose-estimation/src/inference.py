"""
Pose Inference Engine - OpenVINO runtime for 3D Pose Estimation on Intel iGPU.

This engine runs 3D pose estimation using OpenVINO IR models on Intel GPU only.
GPU device selection is controlled via the POSE_3D_DEVICE environment variable,
defaulting to "GPU" for Intel iGPU.
"""

import os
import cv2
import numpy as np
import logging
from pathlib import Path
import openvino as ov

from engine3js import parse_poses

logger = logging.getLogger(__name__)


class PoseInference:
    """3D Pose estimation inference engine using OpenVINO IR on GPU."""

    def __init__(self, model_path: str, device: str = None, device_properties: dict = None):
        """Initialize inference engine.
    
        The model is expected to be an OpenVINO IR (XML) file. Device
        selection is controlled via the POSE_3D_DEVICE environment variable,
        defaulting to "GPU" for Intel iGPU.
        """
    
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"OpenVINO IR model not found: {self.model_path}")
    
        self.core = ov.Core()
    
        # Force GPU usage (like rPPG service)
        if device is None:
            raw_device = os.getenv("POSE_3D_DEVICE", "GPU")
            device = raw_device.strip().strip('"').strip("'")
    
        logger.info(f"Compiling OpenVINO model on device: {device}")
        print(f"[INFO] Target device: {device}")
    
        # Apply device properties if provided (optional GPU optimizations)
        if device_properties:
            self._configure_device_properties(device, device_properties)
    
        try:
            # Compile model for GPU - no fallback for GPU-only operation
            self.compiled_model = self.core.compile_model(str(self.model_path), device)
            self.device = device
            logger.info("✓ 3D pose model loaded successfully on GPU")
            print(f"[INFO] ✓ Successfully loaded model on {device}")
    
        except Exception as e:
            logger.error(f"Failed to load model on {device}: {e}")
            print(f"[ERROR] Failed to load on {device}: {e}")
            # For 3D pose, we want GPU-only operation, so don't fallback
            raise RuntimeError(f"GPU inference required but failed: {e}")
    
        # Get input/output info
        self.input_layer = self.compiled_model.input(0)
        self.input_shape = self.input_layer.shape
    
        # Model configuration
        self.target_size = (self.input_shape[3], self.input_shape[2])  # (width, height)
        self.stride = 8
    
        logger.info(f"  Input shape: {self.input_shape}")
        logger.info(f"  Target size: {self.target_size}")
        print(f"[INFO] Model loaded successfully on {self.device}")
        print(f"[INFO] Input shape: {self.input_shape}")
        print(f"[INFO] Target size: {self.target_size}")

    def _configure_device_properties(self, device: str, device_properties: dict):
        """Configure device-specific properties.
        
        Args:
            device: Device name
            device_properties: Properties dictionary
        """
        logger.info(f"Configuring device properties for {device}")
        print(f"[INFO] Configuring device properties for {device}")

        try:
            if device.upper() == "GPU" and "gpu" in device_properties:
                gpu_props = device_properties["gpu"]

                # Set GPU memory type
                if "memory_type" in gpu_props:
                    self.core.set_property("GPU", {"GPU_MEMORY_TYPE": gpu_props["memory_type"]})
                    logger.info(f"GPU memory type: {gpu_props['memory_type']}")
                    print(f"[CONFIG] GPU memory type: {gpu_props['memory_type']}")

                # Set queue throttling
                if "queue_throttle" in gpu_props:
                    self.core.set_property("GPU", {"GPU_QUEUE_THROTTLE": gpu_props["queue_throttle"]})
                    logger.info(f"GPU queue throttle: {gpu_props['queue_throttle']}")
                    print(f"[CONFIG] GPU queue throttle: {gpu_props['queue_throttle']}")

        except Exception as e:
            logger.warning(f"Failed to set device properties: {e}")
            print(f"[WARNING] Failed to set device properties: {e}")

    def get_device_info(self) -> dict:
        """Get device and model information."""
        return {
            "device": self.device,
            "model_path": str(self.model_path),
            "input_shape": list(self.input_shape),
            "target_size": self.target_size
        }

    def preprocess(self, frame):
        """Preprocess frame for inference.
        
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
        """Extract 2D and 3D poses from model outputs.
        
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
        poses_3d, poses_2d = parse_poses(
            inference_results=(heatmaps, pafs, features),
            input_scale=1.0,
            stride=self.stride,
            fx=focal_length,
            is_video=True
        )

        return poses_3d, poses_2d

    def process_frame(self, frame):
        """Process a single frame on GPU.
        
        Args:
            frame: Input frame (BGR)
            
        Returns:
            annotated_frame: Frame with 2D skeleton overlay
            poses_3d: List of 3D poses
            poses_2d: List of 2D poses
        """
        # Preprocess
        input_tensor, resized_frame = self.preprocess(frame)

        # Run inference on GPU
        result = self.compiled_model(input_tensor)

        # Extract outputs
        heatmaps = result[0][0]  # Remove batch dimension
        pafs = result[1][0]      # Remove batch dimension
        features = result[2][0]  # Remove batch dimension

        # Extract poses
        poses_3d, poses_2d = self.extract_poses(heatmaps, pafs, features, resized_frame)

        # Draw 2D skeleton on frame
        annotated_frame = self.draw_poses(frame, poses_2d, resized_frame)

        return annotated_frame, poses_3d, poses_2d

    def draw_poses(self, frame, poses_2d, resized_frame):
        """Draw 2D skeleton on frame.
        
        Args:
            frame: Original input frame
            poses_2d: List of 2D poses
            resized_frame: The resized frame used for inference
            
        Returns:
            Annotated frame
        """
        annotated = frame.copy()

        # Skeleton connections
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

            # Reshape keypoints
            keypoints = np.array(pose_data[:-1]).reshape((-1, 3)).T
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

    def get_model_info(self) -> dict:
        """Get model metadata."""
        return {
            "device": self.device,
            "model_path": str(self.model_path),
            "input_shape": list(self.input_shape),
            "target_size": self.target_size,
            "stride": self.stride
        }