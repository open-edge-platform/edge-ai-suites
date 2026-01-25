
# Aggregator Service (Python)

This service consumes Vital events streamed from DDS-Bridge via gRPC.

## Steps to run

1. Install dependencies
   pip install -r requirements.txt

2. Generate gRPC code
   python -m grpc_tools.protoc -I proto --python_out=aggregator --grpc_python_out=aggregator proto/vital.proto

3. Run the service
   python aggregator/server.py

OR 

4. Build Dockerfile and run   

The service listens on port 50051.



### Results
# Waveform data
{
  "workload_type": "mdpnp",
  "event_type": "waveform",        // or "numeric"
  "timestamp": 1769354498005,
  "payload": {
    "device_id": "LRnWdqwkmuZWcKcJR3tG71yZtRkpWNMgy6SV",
    "metric": "MDC_ECG_LEAD_III",
    "value": 0.0,
    "waveform": [/* float samples */],
    "waveform_frequency_hz": 200
  }
}

# Numeric data

{
  "workload_type": "mdpnp",
  "event_type": "numeric",
  "timestamp": 1769354500123,
  "payload": {
    "device_id": "DwJR5TAbuoL48uiytUWFffIg972gkpzxpHza",
    "metric": "MDC_ECG_HEART_RATE",
    "value": 72.0
  }
}

