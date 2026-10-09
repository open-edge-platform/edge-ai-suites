#!/bin/bash
curl http://<HOST_IP>:30385/pipelines/user_defined_pipelines/object_tracking_1 -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/VIRAT_S_000101.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_tracking/1",
            "publish_frame":false
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_tracking_1"
        }
    },
    "parameters": {
        "detection-device": "CPU",
        "analytics-properties": {
            "config": "/home/pipeline-server/zones/VIRAT_S_000101.json"
        },
        "loitering-watermark-properties": {
            "loitering-threshold": "5.0"
        }
    }
}'

curl http://<HOST_IP>:30385/pipelines/user_defined_pipelines/object_tracking_2 -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/VIRAT_S_000102.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_tracking/2",
            "publish_frame":false
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_tracking_2"
        }
    },
    "parameters": {
        "detection-device": "CPU",
        "analytics-properties": {
            "config": "/home/pipeline-server/zones/VIRAT_S_000102.json"
        },
        "loitering-watermark-properties": {
            "loitering-threshold": "5.0"
        }
    }
}'

curl http://<HOST_IP>:30385/pipelines/user_defined_pipelines/object_tracking_3 -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/VIRAT_S_000103.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_tracking/3",
            "publish_frame":false
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_tracking_3"
        }
    },
    "parameters": {
        "detection-device": "CPU",
        "analytics-properties": {
            "config": "/home/pipeline-server/zones/VIRAT_S_000103.json"
        },
        "loitering-watermark-properties": {
            "loitering-threshold": "5.0"
        }
    }
}'

curl http://<HOST_IP>:30385/pipelines/user_defined_pipelines/object_tracking_4 -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/VIRAT_S_000104.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_tracking/4",
            "publish_frame":false
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_tracking_4"
        }
    },
    "parameters": {
        "detection-device": "CPU",
        "analytics-properties": {
            "config": "/home/pipeline-server/zones/VIRAT_S_000104.json"
        },
        "loitering-watermark-properties": {
            "loitering-threshold": "5.0"
        }
    }
}'