# How to start MQTT publisher

Bring the services up.

    ```sh
    docker compose up -d
    ```

The below CURL command publishes metadata to the MQTT broker and sends frames over WebRTC for streaming.

Assuming broker is running in the same host over port `1883`, replace the `<HOST_IP>` field with your system IP address.  
WebRTC Stream will be accessible at `https://<HOST_IP>/mediamtx/mqttstream/`.

```sh
curl -k https://<HOST_IP>/api/pipelines/user_defined_pipelines/pcb_anomaly_detection_mqtt -X POST -H 'Content-Type: application/json' -d '{
    "source": {
        "uri": "file:///home/pipeline-server/resources/videos/anomalib_pcb_test.avi",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "publish_frame":true,
            "topic": "pcb_anomaly_detection"
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "mqttstream",
            "overlay": false
        }
    },
    "parameters": {
        "classification-properties": {
            "model": "/home/pipeline-server/resources/models/pcb-anomaly-detection/deployment/Anomaly classification/model/model.xml",
            "device": "CPU"
        }
    }
}'
```
In the above curl command set `publish_frame` to false if you don't want frames sent over MQTT. Metadata will be sent over MQTT.

Output can be viewed on MQTT subscriber as shown below.

```sh
docker run -it --rm \
  --network industrial-edge-insights-vision_mraas \
  --entrypoint mosquitto_sub \
  eclipse-mosquitto:latest \
  -h mqtt-broker -p 1883 -t pcb_anomaly_detection

# Note: Update --network above if it is different in your execution. Network can be found using: docker network ls
```