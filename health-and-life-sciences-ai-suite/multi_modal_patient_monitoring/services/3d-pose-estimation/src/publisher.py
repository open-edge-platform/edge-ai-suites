"""
gRPC Publisher for Pose Data Only (no frame data)
"""

import grpc
from typing import Dict
from proto import pose_pb2, pose_pb2_grpc


class GrpcPosePublisher:
    """Publishes pose data only via gRPC unary calls"""

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
            'total_poses_sent': 0
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
                    # ✅ Smaller message limits since no frame data
                    ('grpc.max_send_message_length', 1 * 1024 * 1024),  # 1MB
                    ('grpc.max_receive_message_length', 1 * 1024 * 1024), # 1MB
                ]
            )
            self.stub = pose_pb2_grpc.PoseServiceStub(self.channel)
            print("[INFO] ✅ gRPC connection established (pose data only - frames via MJPEG)")
        except Exception as e:
            print(f"[ERROR] Failed to connect: {e}")
            self.channel = None
            self.stub = None

    def publish(self, data_packet: Dict) -> bool:
        """
        Publish pose data only (no frame data)
        
        Args:
            data_packet: Dictionary containing pose data only
            
        Returns:
            bool: True if published successfully
        """
        if not self.stub:
            self.stats['total_failed'] += 1
            return False
        
        try:
            # Create PoseFrame message (no frame data)
            pose_frame = self._create_pose_frame(data_packet)
            
            # Send immediately (unary call)
            response = self.stub.PublishPose(pose_frame, timeout=5.0)
            
            if response.ok:
                self.stats['total_sent'] += 1
                # Track poses sent
                self.stats['total_poses_sent'] += data_packet.get('num_persons', 0)
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
        """Create PoseFrame with pose data only (frames via MJPEG streaming)"""
        
        timestamp_ms = data_packet.get("timestamp", 0)
        source_id = data_packet.get("source_id", self.source_id)
        frame_number = data_packet.get("frame_number", 0)
        poses_3d = data_packet.get("poses_3d", [])
        poses_2d = data_packet.get("poses_2d", [])

        # ✅ Create PoseFrame WITHOUT frame_data (using MJPEG streaming instead)
        pose_frame = pose_pb2.PoseFrame(
            timestamp_ms=timestamp_ms,
            source_id=source_id,
            frame_number=frame_number,
            # ✅ NO frame_data field - frames available via MJPEG at localhost:8085
        )

        # Add people data (same as before)
        for i, (pose_3d, pose_2d) in enumerate(zip(poses_3d, poses_2d)):
            person = pose_pb2.PersonPose(person_id=i)
            
            # Add 3D joints
            for joint_data in pose_3d.get('joints_3d', []):
                joint_3d = pose_pb2.Joint3D(
                    x=joint_data.get('x', 0.0),
                    y=joint_data.get('y', 0.0),
                    z=joint_data.get('z', 0.0)
                )
                person.joints_3d.append(joint_3d)
            
            # Add 2D joints  
            for joint_data in pose_2d.get('joints_2d', []):
                joint_2d = pose_pb2.Joint2D(
                    x=joint_data.get('x', 0.0),
                    y=joint_data.get('y', 0.0)
                )
                person.joints_2d.append(joint_2d)
            
            # Add confidence scores
            if 'confidence' in pose_3d:
                person.confidence.extend(pose_3d['confidence'])
                
            pose_frame.people.append(person)
        
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
        
        print("\n[STATS] Publisher Statistics:")
        print(f"  Total sent: {self.stats['total_sent']}")
        print(f"  Total failed: {self.stats['total_failed']}")
        print(f"  Success rate: {success_rate:.1f}%")
        print(f"  Total poses sent: {self.stats['total_poses_sent']}")
        if self.stats['last_error']:
            print(f"  Last error: {self.stats['last_error']}")