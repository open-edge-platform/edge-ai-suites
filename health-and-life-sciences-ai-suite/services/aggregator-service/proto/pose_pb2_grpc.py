import grpc
from . import pose_pb2 as pose__pb2


class PoseServiceStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        self.PublishPose = channel.unary_unary(
                '/pose.PoseService/PublishPose',
                request_serializer=pose__pb2.PoseFrame.SerializeToString,
                response_deserializer=pose__pb2.Ack.FromString,
                _registered_method=True)
        self.StreamPoseData = channel.stream_unary(
                '/pose.PoseService/StreamPoseData',
                request_serializer=pose__pb2.PoseFrame.SerializeToString,
                response_deserializer=pose__pb2.Ack.FromString,
                _registered_method=True)


class PoseServiceServicer(object):
    """Missing associated documentation comment in .proto file."""

    def PublishPose(self, request, context):
        """Unary call - send one frame at a time (more reliable)
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def StreamPoseData(self, request_iterator, context):
        """Streaming call - send multiple frames (kept for future use)
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_PoseServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'PublishPose': grpc.unary_unary_rpc_method_handler(
                    servicer.PublishPose,
                    request_deserializer=pose__pb2.PoseFrame.FromString,
                    response_serializer=pose__pb2.Ack.SerializeToString,
            ),
            'StreamPoseData': grpc.stream_unary_rpc_method_handler(
                    servicer.StreamPoseData,
                    request_deserializer=pose__pb2.PoseFrame.FromString,
                    response_serializer=pose__pb2.Ack.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
        'PoseService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('pose.PoseService', rpc_method_handlers)


 # This class is part of an EXPERIMENTAL API.
class PoseService(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def PublishPose(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/pose.PoseService/PublishPose',
            pose__pb2.PoseFrame.SerializeToString,
            pose__pb2.Ack.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def StreamPoseData(request_iterator,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.stream_unary(
            request_iterator,
            target,
            '/pose.PoseService/StreamPoseData',
            pose__pb2.PoseFrame.SerializeToString,
            pose__pb2.Ack.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)
