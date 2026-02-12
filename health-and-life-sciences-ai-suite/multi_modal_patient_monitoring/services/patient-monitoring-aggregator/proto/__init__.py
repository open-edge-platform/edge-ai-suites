"""Proto package for gRPC service definitions"""

# Import the generated protobuf modules
from . import vital_pb2
from . import vital_pb2_grpc
from . import pose_pb2
from . import pose_pb2_grpc

# Make them available at package level
__all__ = [
    'vital_pb2',
    'vital_pb2_grpc',
    'pose_pb2',
    'pose_pb2_grpc',
]
