
# Aggregator Service (Python)

This service consumes Vital events streamed from DDS-Bridge via gRPC.

## Steps to run

1. Install dependencies
   pip install -r requirements.txt

2. Generate gRPC code
   python -m grpc_tools.protoc -I proto --python_out=aggregator --grpc_python_out=aggregator proto/vital.proto

3. Run the service
   python aggregator/server.py

The service listens on port 50051.
