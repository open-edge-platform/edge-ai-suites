# Configure Alerts in Time Series Analytics Microservice

This section provides instructions for setting up alerts in **Time Series Analytics Microservice**.

## Docker Compose Deployment

### Docker - Publish MQTT Alerts

#### Configure MQTT Alerts

By default, the following MQTT alerts are configured in `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal/configs/time-series-analytics-microservice/config.json` file.

  ```json
    "alerts": {
        "mqtt": {
            "mqtt_broker_host": "ia-mqtt-broker",
            "mqtt_broker_port": 1883,
            "name": "my_mqtt_broker"
        }
     }
   ```

#### Configure MQTT Alert in TICK Script

The following snippet shows how to add the MQTT if not 
already added. By default, the `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal/configs/time-series-analytics-microservice/tick_scripts/weld_anomaly_detector.tick` TICK Script has the following configuration done by default.

```bash
@weld_anomaly_detector()
|alert()
    .crit(lambda: "anomaly_status" > 0)
    .message('{"time": "{{ index .Time }}", "Pressure": {{ index .Fields "Pressure" }}, "CO2 Weld Flow": {{ index .Fields "CO2 Weld Flow" }}, "anomaly_status": {{ index .Fields "anomaly_status" }} } ')
    .noRecoveries()
    .mqtt('my_mqtt_broker')
    .topic('alerts/weld_defect_detection')
    .qos(1)
```

> **Note**: Setting **QoS** to `1` ensures messages are delivered at least once. Alerts are preserved and resent if the MQTT broker reconnects after downtime.

### Docker - Subscribe to MQTT Alerts

Follow the steps to subscribe to the published MQTT alerts.

- To subscribe to all MQTT topics, execute the following command:

```sh
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t '#' -p 1883
```

#### Docker - Subscribing to Time Series Analytics Microservice Alerts

```sh
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t alerts/weld_defect_detection -p 1883
```

#### Docker - Subscribing to DLStreamer Pipeline Server Results

```sh
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t vision_weld_defect_classification -p 1883
```

#### Docker - Subscribing to Fusion Analytics Results

```sh
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t fusion/anomaly_detection_results -p 1883
```

## Helm Deployment

### Helm - Publish MQTT Alerts

For detailed instructions on configuring and publishing MQTT alerts, refer to the [Publish MQTT Alerts](#docker---publish-mqtt-alerts) section.

### Helm - Subscribe to MQTT Alerts

Follow the steps to subscribe to the published MQTT alerts.

To subscribe to MQTT topics in a Helm deployment, execute the following command:

- Identify the MQTT broker pod name by running:

```sh
kubectl get pods -n multimodal-sample-app | grep mqtt-broker
```

- Use the pod name from the output of the above command to subscribe to all topics:
```sh
kubectl exec -it -n multimodal-sample-app <mqtt_broker_pod_name> -- mosquitto_sub -h localhost -v -t '#' -p 1883
```

#### Helm - Subscribing to Time Series Analytics Microservice Alerts

```sh
kubectl exec -it -n multimodal-sample-app <mqtt_broker_pod_name> -- mosquitto_sub -h localhost -v -t alerts/weld_defect_detection -p 1883
```

#### Helm - Subscribing to DLStreamer Pipeline Server Results

```sh
kubectl exec -it -n multimodal-sample-app <mqtt_broker_pod_name> -- mosquitto_sub -h localhost -v -t vision_weld_defect_classification -p 1883
```

#### Helm - Subscribing to Fusion Analytics Results

```sh
kubectl exec -it -n multimodal-sample-app <mqtt_broker_pod_name> -- mosquitto_sub -h localhost -v -t fusion/anomaly_detection_results -p 1883
```

## Supporting Resources

- [Kapacitor MQTT Alert Documentation](https://docs.influxdata.com/kapacitor/v1/reference/event_handlers/mqtt/).
