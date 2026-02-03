"""
gRPC Publisher for Pose Data
Sends pose estimation results frame-by-frame (unary calls)
"""

import grpc
import base64
from typing import Dict
from proto import pose_pb2, pose_pb2_grpc


class GrpcPosePublisher:
    """Publishes pose data via gRPC unary calls (one frame at a time)"""

    def __init__(self, aggregator_address: str, source_id: str = "3d-pose-camera-1"):
        """
        Initialize gRPC publisher
        
        Args:
            aggregator_address: Address of aggregator (e.g., "localhost:50051")
            source_id: Identifier for this video source
        """
        self.aggregator_address = aggregator_address
        self.source_id = source_id
        self.channel = None
        self.stub = None
        
        # Statistics
        self.stats = {
            'total_sent': 0,
            'total_failed': 0,
            'last_error': None,
            'total_bytes_sent': 0
        }
        
        # Connect
        self.connect()

    def connect(self):
        """Establish gRPC connection"""
        try:
            print(f"[INFO] Connecting to aggregator at {self.aggregator_address}")
            self.channel = grpc.insecure_channel(
                self.aggregator_address,
                options=[
                    ('grpc.keepalive_time_ms', 10000),
                    ('grpc.keepalive_timeout_ms', 5000),
                    ('grpc.keepalive_permit_without_calls', True),
                    ('grpc.max_send_message_length', 50 * 1024 * 1024),  # 50MB
                    ('grpc.max_receive_message_length', 50 * 1024 * 1024),
                ]
            )
            self.stub = pose_pb2_grpc.PoseServiceStub(self.channel)
            print("[INFO] gRPC connection established")
        except Exception as e:
            print(f"[ERROR] Failed to connect: {e}")
            self.channel = None
            self.stub = None

    def publish(self, data_packet: Dict) -> bool:
        """
        Publish a single frame immediately (unary call)
        
        Args:
            data_packet: Dictionary containing pose data
            
        Returns:
            bool: True if published successfully
        """
        if not self.stub:
            self.stats['total_failed'] += 1
            return False
        
        try:
            # Create PoseFrame message
            pose_frame = self._create_pose_frame(data_packet)
            
            # Send immediately (unary call)
            response = self.stub.PublishPose(pose_frame, timeout=5.0)
            
            if response.ok:
                self.stats['total_sent'] += 1
                # Track bytes sent (approximate)
                if 'frame_base64' in data_packet:
                    self.stats['total_bytes_sent'] += len(data_packet['frame_base64'])
                return True
            else:
                self.stats['total_failed'] += 1
                self.stats['last_error'] = response.message
                return False
                
        except grpc.RpcError as e:
            self.stats['total_failed'] += 1
            self.stats['last_error'] = f"gRPC error: {e.code()}"
            if self.stats['total_failed'] % 100 == 0:  # Log every 100 failures
                print(f"[ERROR] Failed to publish: {e.code()}")
            return False
        except Exception as e:
            self.stats['total_failed'] += 1
            self.stats['last_error'] = str(e)
            if self.stats['total_failed'] % 100 == 0:
                print(f"[ERROR] Failed to publish: {e}")
            return False

    def _create_pose_frame(self, data_packet: Dict) -> pose_pb2.PoseFrame:
        """
        Convert data packet to PoseFrame protobuf message
        
        Args:
            data_packet: Dictionary with pose data
            
        Returns:
            pose_pb2.PoseFrame: Protobuf message
        """
        # Extract data from packet
        timestamp_ms = data_packet.get("timestamp", 0)
        source_id = data_packet.get("source_id", self.source_id)
        frame_number = data_packet.get("frame_number", 0)
        
        poses_3d = data_packet.get("poses_3d", [])
        poses_2d = data_packet.get("poses_2d", [])
        
        # Extract and decode frame data
        frame_base64 = data_packet.get("frame_base64", "")
        frame_data = base64.b64decode(frame_base64) if frame_base64 else b""
        
        # Create PoseFrame message
        pose_frame = pose_pb2.PoseFrame(
            timestamp_ms=timestamp_ms,
            source_id=source_id,
            frame_data=frame_data,
            frame_number=frame_number
        )
        
        # Merge 2D and 3D poses by person_id
        person_poses = {}
        
        # Process 3D poses
        for pose_3d_data in poses_3d:
            person_id = pose_3d_data.get("person_id", 0)
            joints_3d = pose_3d_data.get("joints_3d", [])
            confidence = pose_3d_data.get("confidence", [])
            
            if person_id not in person_poses:
                person_poses[person_id] = {
                    'person_id': person_id,
                    'joints_2d': [],
                    'joints_3d': [],
                    'confidence': confidence
                }
            
            # Add 3D joints
            for joint in joints_3d:
                joint_3d = pose_pb2.Joint3D(
                    x=float(joint.get("x", 0.0)),
                    y=float(joint.get("y", 0.0)),
                    z=float(joint.get("z", 0.0))
                )
                person_poses[person_id]['joints_3d'].append(joint_3d)
            
            person_poses[person_id]['confidence'] = confidence
        
        # Process 2D poses
        for pose_2d_data in poses_2d:
            person_id = pose_2d_data.get("person_id", 0)
            joints_2d = pose_2d_data.get("joints_2d", [])
            confidence = pose_2d_data.get("confidence", [])
            
            if person_id not in person_poses:
                person_poses[person_id] = {
                    'person_id': person_id,
                    'joints_2d': [],
                    'joints_3d': [],
                    'confidence': confidence
                }
            
            # Add 2D joints
            for joint in joints_2d:
                joint_2d = pose_pb2.Joint2D(
                    x=float(joint.get("x", 0.0)),
                    y=float(joint.get("y", 0.0))
                )
                person_poses[person_id]['joints_2d'].append(joint_2d)
            
            # Use 2D confidence if 3D not available
            if not person_poses[person_id]['confidence']:
                person_poses[person_id]['confidence'] = confidence
        
        # Create PersonPose messages and add to PoseFrame
        for person_data in person_poses.values():
            person_pose = pose_pb2.PersonPose(
                person_id=person_data['person_id']
            )
            
            # Add joints_2d
            for joint_2d in person_data['joints_2d']:
                person_pose.joints_2d.append(joint_2d)
            
            # Add joints_3d
            for joint_3d in person_data['joints_3d']:
                person_pose.joints_3d.append(joint_3d)
            
            # Add confidence values
            for conf in person_data['confidence']:
                person_pose.confidence.append(float(conf))
            
            pose_frame.people.append(person_pose)
        
        return pose_frame

    def close(self):
        """Close gRPC connection"""
        print("[INFO] Shutting down publisher...")
        if self.channel:
            self.channel.close()
            print("[INFO] gRPC channel closed")

    def print_stats(self):
        """Print publishing statistics"""
        total = self.stats['total_sent'] + self.stats['total_failed']
        success_rate = (self.stats['total_sent'] / total * 100) if total > 0 else 0
        total_mb = self.stats['total_bytes_sent'] / (1024 * 1024)
        
        print("\n[STATS] Publisher Statistics:")
        print(f"  Total sent: {self.stats['total_sent']}")
        print(f"  Total failed: {self.stats['total_failed']}")
        print(f"  Success rate: {success_rate:.1f}%")
        print(f"  Total data sent: {total_mb:.2f} MB")
        if self.stats['last_error']:
            print(f"  Last error: {self.stats['last_error']}")