import grpc
from concurrent import futures
from google.protobuf.empty_pb2 import Empty

import vital_pb2
import vital_pb2_grpc
from .consumer import VitalConsumer


class VitalService(vital_pb2_grpc.VitalServiceServicer):
    def __init__(self):
        self.consumer = VitalConsumer()

    def StreamVitals(self, request_iterator, context):
        for vital in request_iterator:
            self.consumer.consume(vital)
        return Empty()

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    vital_pb2_grpc.add_VitalServiceServicer_to_server(
        VitalService(), server
    )
    server.add_insecure_port("[::]:50051")
    server.start()
    print("Aggregator service running on port 50051")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
