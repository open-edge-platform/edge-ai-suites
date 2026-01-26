import grpc
from proto import pose_pb2, pose_pb2_grpc


class PoseGrpcPublisher:
    def __init__(self, address="localhost:50051"):
        self.channel = grpc.insecure_channel(address)
        self.stub = pose_pb2_grpc.PoseServiceStub(self.channel)

    def send(self, pose_frame):
        """
        Push PoseFrame proto to server as a unary RPC
        """
        try:
            # Unary RPC defined in pose.proto: PublishPose(PoseFrame) returns Ack
            self.stub.PublishPose(pose_frame)
        except Exception as e:
            print(f"❌ gRPC send failed: {e}")

    def close(self):
        self.channel.close()
