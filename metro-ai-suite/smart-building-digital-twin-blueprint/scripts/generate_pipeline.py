#!/usr/bin/env python3
"""Generate DL Streamer pipeline configuration for detected cameras"""

import json
import sys
import argparse
from pathlib import Path


PIPELINE_TEMPLATE = """rtspsrc location=rtsp://mediaserver:8554/{cam_id} latency=200 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! video/x-raw,format=BGR ! sscape_timestamp_capture name=timesync ntp-server=ntpserv ! gvadetect model=/models/model.xml device={device} ! gvametaconvert add-tensor-data=true name=metaconvert ! sscape_post_inference_data_publish name=datapublisher ! appsink sync=true drop=true max-buffers=1"""


def generate_pipeline(camera_ids, device="GPU", output_path=None):
  """Generate pipeline configuration for multiple cameras"""
  
  pipelines = {
    "config": {
      "logging": {
        "C_LOG_LEVEL": "INFO",
        "PY_LOG_LEVEL": "INFO"
      },
      "pipelines": []
    }
  }
  
  for cam_id in camera_ids:
    pipeline_str = PIPELINE_TEMPLATE.format(
      cam_id=cam_id,
      device=device
    )
    
    pipeline_entry = {
      "name": f"showcase-{cam_id}",
      "source": "gstreamer",
      "pipeline": pipeline_str,
      "auto_start": True,
      "parameters": {
        "type": "object",
        "properties": {
          "ntp_server": {
            "element": {"name": "timesync", "property": "ntp-server"},
            "type": "string"
          },
          "cameraid": {
            "element": {"name": "datapublisher", "property": "cameraid"},
            "type": "string"
          },
          "metadatagenpolicy": {
            "element": {"name": "datapublisher", "property": "metadatagenpolicy"},
            "type": "string"
          },
          "detection_labels": {
            "element": {"name": "datapublisher", "property": "detection-labels"},
            "type": "string"
          }
        }
      },
      "payload": {
        "parameters": {
          "ntp_server": "ntpserv",
          "cameraid": cam_id,
          "metadatagenpolicy": "detectionPolicy",
          "detection_labels": "person,door,luggage"
        }
      }
    }
    
    pipelines["config"]["pipelines"].append(pipeline_entry)
  
  if output_path:
    with open(output_path, 'w') as f:
      json.dump(pipelines, f, indent=2)
    print(f"✓ Generated pipeline for {len(camera_ids)} cameras: {', '.join(camera_ids)}")
  
  return pipelines


def main():
  parser = argparse.ArgumentParser(
    description='Generate DL Streamer pipeline configuration'
  )
  parser.add_argument('--cameras', nargs='+', required=True,
                       help='Camera IDs (e.g., cam-1 cam-2 cam-3)')
  parser.add_argument('--device', default='GPU',
                       choices=['GPU', 'CPU'],
                       help='Inference device')
  parser.add_argument('--output', required=True,
                       help='Output pipeline JSON file')
  
  args = parser.parse_args()
  
  try:
    generate_pipeline(args.cameras, args.device, args.output)
  except Exception as e:
    print(f"ERROR: Pipeline generation failed: {e}", file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
  main()
