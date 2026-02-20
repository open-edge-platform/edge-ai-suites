"""
Pose Data Encoder - Modified for pose-only data (no frames)
"""

import numpy as np
from typing import List, Dict, Any
import time


class PoseEncoder:
    """Encodes pose estimation data for transmission (pose data only)"""

    def __init__(self, source_id: str = "3d-pose-camera-1"):
        """
        Initialize encoder

        Args:
            source_id: Identifier for this video source
        """
        self.source_id = source_id
        self.num_joints = 19  # ✅ ADD THIS LINE - COCO format has 19 joints

    # ✅ ADD THIS NEW METHOD
    def detect_activity(self, joints_3d: List[Dict]) -> str:
        """
        Simple activity detection based on 3D joint positions
        
        Args:
            joints_3d: List of 3D joint positions with x, y, z coordinates
            
        Returns:
            Activity label string
        """
        if not joints_3d or len(joints_3d) < 15:
            return "Unknown"
        
        try:
            # Filter valid joints (exclude invalid joints marked as -1)
            valid_joints = [j for j in joints_3d if j['x'] != -1.0 and j['y'] != -1.0 and j['z'] != -1.0]
            
            if len(valid_joints) < 10:
                return "Unknown"
            
            # Get key joints using COCO format indices:
            # 1: left shoulder, 2: right shoulder
            # 9: left hip, 10: right hip
            # 12: left knee, 13: right knee
            
            # Calculate average positions for stability
            shoulder_y = (joints_3d[1]['y'] + joints_3d[2]['y']) / 2 if len(joints_3d) > 2 else 0
            hip_y = (joints_3d[9]['y'] + joints_3d[10]['y']) / 2 if len(joints_3d) > 10 else 0
            knee_y = (joints_3d[12]['y'] + joints_3d[13]['y']) / 2 if len(joints_3d) > 13 else 0
            
            # Calculate torso height and body angles
            torso_height = abs(shoulder_y - hip_y)
            hip_knee_distance = abs(hip_y - knee_y)
            
            # Activity classification based on body geometry
            if torso_height < 30:  # Torso compressed
                return "Sitting"
            elif hip_knee_distance < 20:  # Legs bent significantly
                return "Sitting"
            elif torso_height > 60 and hip_knee_distance > 30:  # Upright posture
                return "Standing"
            elif torso_height > 40:  # Moderate torso extension
                return "Walking"
            else:
                return "Moving"
                
        except Exception as e:
            print(f"[Activity Detection] Error: {e}")
            return "Unknown"

    def encode_poses_3d(self, poses_3d: List) -> List[Dict]:
        """
        Encode 3D poses to dictionary format
        
        ✅ Returns ALL 19 joints with their estimated positions, regardless of confidence
        """
        encoded_poses = []

        for person_id, pose_3d in enumerate(poses_3d):
            if pose_3d is None or len(pose_3d) == 0:
                continue

            # Convert to numpy array if needed
            pose_array = np.array(pose_3d) if not isinstance(pose_3d, np.ndarray) else pose_3d

            # Reshape to (num_joints, 4) if flat
            if len(pose_array.shape) == 1:
                pose_array = pose_array.reshape((-1, 4))

            # ✅ Initialize all 19 joints with invalid values
            joints_3d = [{"x": -1.0, "y": -1.0, "z": -1.0, "visibility": 0.0} for _ in range(self.num_joints)]
            confidence = [-1.0 for _ in range(self.num_joints)]

            # ✅ Fill in ALL joints, including low-confidence ones
            for joint_idx, joint_data in enumerate(pose_array):
                if joint_idx >= self.num_joints:
                    break
            
                x, y, z, conf = joint_data[:4]

                # ✅ CHANGED: Include ALL joints, even with low confidence
                # Only mark as invalid if coordinates are actually invalid (NaN, inf, etc.)
                is_valid = not (np.isnan(x) or np.isnan(y) or np.isnan(z) or 
                              np.isinf(x) or np.isinf(y) or np.isinf(z))
                
                if is_valid:
                    joints_3d[joint_idx] = {
                        "x": float(x),
                        "y": float(y),
                        "z": float(z),
                        "visibility": float(conf)  # ✅ Store confidence as visibility
                    }
                    confidence[joint_idx] = float(conf)
                else:
                    # Only use -1 if coordinates are truly invalid
                    joints_3d[joint_idx] = {
                        "x": -1.0,
                        "y": -1.0,
                        "z": -1.0,
                        "visibility": 0.0
                    }
                    confidence[joint_idx] = 0.0

            # ✅ Always append all 19 joints
            encoded_poses.append({
                "person_id": person_id,
                "joints_3d": joints_3d,
                "confidence": confidence,
            })

        return encoded_poses

    def encode_poses_2d(self, poses_2d: List) -> List[Dict]:
        """
        Encode 2D poses to dictionary format

        Args:
            poses_2d: List of 2D pose data from inference

        Returns:
            List of pose dictionaries with 2D keypoints
        """
        encoded_poses = []

        for person_id, pose_2d in enumerate(poses_2d):
            if len(pose_2d) == 0:
                continue

            # Parse keypoints: [x0, y0, conf0, x1, y1, conf1, ..., overall_score]
            num_joints = (len(pose_2d) - 1) // 3

            joints_2d = []
            confidence = []

            for j in range(num_joints):
                x = pose_2d[j * 3]
                y = pose_2d[j * 3 + 1]
                conf = pose_2d[j * 3 + 2]

                joints_2d.append({
                    "x": float(x) if conf > 0 else -1.0,
                    "y": float(y) if conf > 0 else -1.0,
                })
                confidence.append(float(conf))

            # Overall score
            overall_score = pose_2d[-1] if len(pose_2d) > 0 else 0.0

            encoded_poses.append({
                "person_id": person_id,
                "joints_2d": joints_2d,
                "confidence": confidence,
                "overall_score": float(overall_score),
            })

        return encoded_poses

    # ✅ MODIFY: Remove frame_bytes parameter since we don't send frames
    def encode_data(self, poses_3d: List, poses_2d: List, frame_number: int = 0) -> Dict[str, Any]:
        """
        Encode pose data only for aggregator (no frame data - using MJPEG streaming instead)

        Args:
            poses_3d: List of 3D poses
            poses_2d: List of 2D poses
            frame_number: Frame sequence number

        Returns:
            Data packet dictionary with pose data only (no frame bytes)
        """
        # Encode poses
        encoded_3d = self.encode_poses_3d(poses_3d)
        encoded_2d = self.encode_poses_2d(poses_2d)

        # Detect activity from first person's pose
        activity = "Unknown"
        if len(encoded_3d) > 0 and 'joints_3d' in encoded_3d[0]:
            activity = self.detect_activity(encoded_3d[0]['joints_3d'])

        # ✅ Data packet with pose data only - frames via MJPEG at localhost:8085
        data_packet = {
            "timestamp": int(time.time() * 1000),
            "source_id": self.source_id,
            "frame_number": frame_number,
            "poses_3d": encoded_3d,
            "poses_2d": encoded_2d,
            "num_persons": len(encoded_3d),
            "activity": activity,
            # ✅ NO frame_bytes - using MJPEG streaming instead
        }

        return data_packet