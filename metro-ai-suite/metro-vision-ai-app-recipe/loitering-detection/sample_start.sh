#!/bin/bash
curl -k https://localhost/api/pipelines/user_defined_pipelines/object_tracking_1 -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/VIRAT_S_000101.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_tracking_1",
            "publish_frame":false
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_tracking_1"
        }
    },
    "parameters": {
        "detection-device": "CPU"
    }
}'

curl -k https://localhost/api/pipelines/user_defined_pipelines/object_tracking_2 -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/VIRAT_S_000102.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_tracking_2",
            "publish_frame":false
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_tracking_2"
        }
    },
    "parameters": {
        "detection-device": "CPU"
    }
}'

curl -k https://localhost/api/pipelines/user_defined_pipelines/object_tracking_3 -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/VIRAT_S_000103.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_tracking_3",
            "publish_frame":false
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_tracking_3"
        }
    },
    "parameters": {
        "detection-device": "CPU"
    }
}'

curl -k https://localhost/api/pipelines/user_defined_pipelines/object_tracking_4 -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/VIRAT_S_000104.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_tracking_4",
            "publish_frame":false
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_tracking_4"
        }
    },
    "parameters": {
        "detection-device": "CPU"
    }
}'
