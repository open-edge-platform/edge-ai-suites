#!/bin/bash
curl http://<HOST_IP>:30485/pipelines/user_defined_pipelines/yolov11s_1_cpu -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/new_video_1.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_detection_1",
            "publish_frame":false
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

curl http://<HOST_IP>:30485/pipelines/user_defined_pipelines/yolov11s_1_cpu -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/new_video_2.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_detection_2",
            "publish_frame":false
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

curl http://<HOST_IP>:30485/pipelines/user_defined_pipelines/yolov11s_1_cpu -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/new_video_3.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_detection_3",
            "publish_frame":false
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

curl http://<HOST_IP>:30485/pipelines/user_defined_pipelines/yolov11s_1_cpu -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/new_video_4.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_detection_4",
            "publish_frame":false
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