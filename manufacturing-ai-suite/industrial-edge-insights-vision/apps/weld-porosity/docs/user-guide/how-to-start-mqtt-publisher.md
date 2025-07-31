# How to start MQTT publisher

Pre-requisites:
- Configure and start MQTT broker

Start the MQTT broker [eclipse mosquitto](https://mosquitto.org/) using configuration `configs/mosquitto.conf` in the application directory as below.

  ```sh
  cd <WORKDIR>/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/apps/weld-porosity
  docker run -d --name=mqtt_broker -p 1883:1883 -v $PWD/configs/mosquitto.conf:/mosquitto/config/mosquitto.conf eclipse-mosquitto
  ```

With the above configuration, the broker listens on port `1883`.

- `MQTT_HOST` and `MQTT_PORT` environment variable must be set for DL Streamer Pipeline Server prior to sending this curl request.
    You can add them to the `environments` for DL Streamer Pipeline Server section in `docker-compose.yml`.
    ```yaml
    dlstreamer-pipeline-server:
      environment:
        MQTT_HOST: <HOST_IP>
        MQTT_PORT: 1883
    ```

The below CURL command publishes metadata to a MQTT broker and sends frames over WebRTC for streaming.

Assuming broker is running in the same host over port `1883`, replace the `<HOST_IP>` field with your system IP address.  
WebRTC Stream will be accessible at `http://<HOST_IP>:8889/mqttstream`.

```sh
curl http://<HOST_IP>:8080/pipelines/user_defined_pipelines/weld_porosity_classification_mqtt -X POST -H 'Content-Type: application/json' -d '{
    "source": {
        "uri": "file:///home/pipeline-server/resources/videos/welding.avi",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "publish_frame":true,
            "topic": "weld_porosity_classification"
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "mqttstream",
            "overlay": false
        }
    },
    "parameters": {
        "classification-properties": {
            "model": "/home/pipeline-server/resources/models/weld-porosity/deployment/Classification/model/model.xml",
            "device": "CPU"
        }
    }
}'
```
In the above curl command set `publish_frame` to false if you don't want frames sent over MQTT. Metadata will be sent over MQTT.

Output can be viewed on MQTT subscriber as shown below.

```sh
docker run -it --entrypoint mosquitto_sub eclipse-mosquitto:latest --topic weld_porosity_classification -p 1883 -h <HOST_IP>
```