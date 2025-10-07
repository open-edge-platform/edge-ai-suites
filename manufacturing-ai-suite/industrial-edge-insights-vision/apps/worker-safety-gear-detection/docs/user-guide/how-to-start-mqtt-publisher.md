# How to start MQTT publisher

Bring the services up.

    ```sh
    docker compose up -d
    ```

The below CURL command publishes metadata to the MQTT broker and sends frames over WebRTC for streaming.

Assuming broker is running in the same host over port `1883`, replace the `<HOST_IP>` field with your system IP address.  
WebRTC Stream will be accessible at `https://<HOST_IP>/mediamtx/mqttstream/`.

```sh
curl -k https://<HOST_IP>/api/pipelines/user_defined_pipelines/worker_safety_gear_detection_mqtt -X POST -H 'Content-Type: application/json' -d '{
    "source": {
        "uri": "file:///home/pipeline-server/resources/videos/Safety_Full_Hat_and_Vest.avi",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "publish_frame":true,
            "topic": "worker_safety_gear_detection"
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "mqttstream",
            "overlay": false
        }
    },
    "parameters": {
        "detection-properties": {
            "model": "/home/pipeline-server/resources/models/worker-safety-gear-detection/deployment/Detection/model/model.xml",
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
  -h mqtt-broker -p 1883 -t worker_safety_gear_detection

# Note: Update --network above if it is different in your execution. Network can be found using: docker network ls
```