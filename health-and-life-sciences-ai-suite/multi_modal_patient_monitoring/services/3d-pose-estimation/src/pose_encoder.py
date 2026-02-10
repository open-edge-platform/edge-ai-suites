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

    def encode_poses_3d(self, poses_3d: List) -> List[Dict]:
        """Encode 3D poses to dictionary format"""
        encoded_poses = []

        for person_id, pose_3d in enumerate(poses_3d):
            if pose_3d is None or len(pose_3d) == 0:
                continue

            # Convert to numpy array if needed
            pose_array = np.array(pose_3d) if not isinstance(pose_3d, np.ndarray) else pose_3d

            # Reshape to (num_joints, 4) if flat
            if len(pose_array.shape) == 1:
                pose_array = pose_array.reshape((-1, 4))

            # Extract joints
            joints_3d = []
            confidence = []

            for joint_data in pose_array:
                x, y, z, conf = joint_data[:4]

                if conf > 0:
                    joints_3d.append({"x": float(x), "y": float(y), "z": float(z)})
                    confidence.append(float(conf))
                else:
                    joints_3d.append({"x": -1.0, "y": -1.0, "z": -1.0})
                    confidence.append(-1.0)

            if len(joints_3d) > 0:
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

    def encode_data(self, poses_3d: List, poses_2d: List, frame_number: int = 0) -> Dict[str, Any]:
        """
        Encode pose data only (no frame data)

        Args:
            poses_3d: List of 3D poses
            poses_2d: List of 2D poses
            frame_number: Frame sequence number

        Returns:
            Data packet dictionary with pose data only
        """
        # Encode poses
        encoded_3d = self.encode_poses_3d(poses_3d)
        encoded_2d = self.encode_poses_2d(poses_2d)

        # Create data packet (no frame data)
        data_packet = {
            "timestamp": int(time.time() * 1000),  # Milliseconds
            "source_id": self.source_id,
            "frame_number": frame_number,
            "poses_3d": encoded_3d,
            "poses_2d": encoded_2d,
            "num_persons": len(encoded_3d),
        }

        return data_packet