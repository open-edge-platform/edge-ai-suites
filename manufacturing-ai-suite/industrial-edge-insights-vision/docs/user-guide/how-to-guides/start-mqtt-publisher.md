# Start MQTT Publisher in Vision AI Detection Apps

Bring the services up.

> **Note:** If you are running multiple instances of the application, start the services using `./run.sh up` instead.

```sh
docker compose up -d
```

The below CURL command publishes metadata to the MQTT broker and sends frames over WebRTC for streaming.

Assuming broker is running in the same host over port `1883`, replace the `<HOST_IP>` field with your system IP address.
WebRTC Stream will be accessible at `https://<HOST_IP>/mediamtx/mqttstream/`.

> **Note:** If you are running multiple instances of the application, ensure to provide `NGINX_HTTPS_PORT` number in the URL for the app instance, i.e., replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`
> If you are running a single instance and using an `NGINX_HTTPS_PORT` other than the default 443, replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`.

<!--hide_directive ::::{tab-set} hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **Pallet Defect Detection**
<!--hide_directive :sync: pallet-detect hide_directive-->

```sh
curl -k https://<HOST_IP>/api/pipelines/user_defined_pipelines/pallet_defect_detection_mqtt -X POST -H 'Content-Type: application/json' -d '{
    "source": {
        "uri": "file:///home/pipeline-server/resources/videos/warehouse.avi",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "publish_frame":true,
            "topic": "pallet_defect_detection"
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "mqttstream",
            "overlay": false
        }
    },
    "parameters": {
        "detection-properties": {
            "model": "/home/pipeline-server/resources/models/pallet-defect-detection/deployment/Detection/model/model.xml",
            "device": "CPU"
        }
    }
}'
```

<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
<!--hide_directive :sync: pcb-detect hide_directive-->

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

<!--hide_directive
:::
::::
hide_directive-->

In the above curl command set `publish_frame` to `false` if you do not want frames sent over MQTT. Metadata will be sent over MQTT.

Output can be viewed on MQTT subscriber as shown below.

<!--hide_directive ::::{tab-set} hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **Pallet Defect Detection**
<!--hide_directive :sync: pallet-detect hide_directive-->

```sh
docker run -it --rm \
  --network industrial-edge-insights-vision_industrial-edge-vision \
  --entrypoint mosquitto_sub \
  eclipse-mosquitto:latest \
  -h mqtt-broker -p 1883 -t pallet_defect_detection

# Note:
# Update --network above if it is different in your execution. Network can be found using: docker network ls
# Update --network as <INSTANCE_NAME>_industrial-edge-vision for multi-instance setup
```

<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
<!--hide_directive :sync: pcb-detect hide_directive-->

```sh
docker run -it --rm \
  --network industrial-edge-insights-vision_industrial-edge-vision \
  --entrypoint mosquitto_sub \
  eclipse-mosquitto:latest \
  -h mqtt-broker -p 1883 -t pcb_anomaly_detection

# Note:
# Update --network above if it is different in your execution. Network can be found using: docker network ls
# Update --network as <INSTANCE_NAME>_industrial-edge-vision for multi-instance setup
```

<!--hide_directive
:::
::::
hide_directive-->
