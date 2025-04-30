#!/bin/bash
curl http://<HOST_IP>:30107/pipelines/user_defined_pipelines/yolov10_1_cpu -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/new_video_1.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "host": "<HOST_IP>:31883",
            "topic": "object_detection_1",
            "timeout": 1000
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_detection_1"
        }
    },
    "parameters": {
        "detection-device": "CPU"
    }
}'

curl http://<HOST_IP>:30107/pipelines/user_defined_pipelines/yolov10_1_cpu -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/new_video_2.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "host": "<HOST_IP>:31883",
            "topic": "object_detection_2",
            "timeout": 1000
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_detection_2"
        }
    },
    "parameters": {
        "detection-device": "CPU"
    }
}'

curl http://<HOST_IP>:30107/pipelines/user_defined_pipelines/yolov10_1_cpu -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/new_video_3.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "host": "<HOST_IP>:31883",
            "topic": "object_detection_3",
            "timeout": 1000
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_detection_3"
        }
    },
    "parameters": {
        "detection-device": "CPU"
    }
}'

curl http://<HOST_IP>:30107/pipelines/user_defined_pipelines/yolov10_1_cpu -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/new_video_4.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "host": "<HOST_IP>:31883",
            "topic": "object_detection_4",
            "timeout": 1000
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_detection_4"
        }
    },
    "parameters": {
        "detection-device": "CPU"
    }
}'