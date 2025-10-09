# Configure Alerts in Time Series Analytics Microservice

This section provides instructions for setting up alerts in **Time Series Analytics Microservice**.

## Docker Compose Deployment

### Publish MQTT Alerts

#### Configure MQTT Alerts

By default, the following MQTT alerts is configured in `edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/time-series-analytics-microservice/config.json` file.

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
already added. By default, the `edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/time-series-analytics-microservice/tick_scripts/weld_anomaly_detector.tick` TICK Script has the following configuration done by default.

```bash
@weld_anomaly_detector()
|alert()
    .crit(lambda: "anomaly_status" > 0)
    .message('Anomaly detected: Wind Speed: {{ index .Fields "wind_speed" }}, Grid Active Power: {{ index .Fields "grid_active_power" }}, Anomaly Status: {{ index .Fields "anomaly_status" }}')
    .mqtt('my_mqtt_broker')
    .topic('alerts/wind_turbine')
    .qos(1)
```

> **Note**: Setting **QoS** to `1` ensures messages are delivered at least once. Alerts are preserved and resent if the MQTT broker reconnects after downtime.

### Subscribing to MQTT Alerts

Follow the steps to subscribe to the published MQTT alerts.

- To subscribe to all MQTT topics, execute the following command:

```sh
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t '#' -p 1883
```

- To subscribe to a specific MQTT topic, such as `alerts/wind_turbine`, use the following command. Note that the topic information can be found in the TICKScript:

```sh
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t alerts/wind_turbine -p 1883
```

## Supporting Resources

- [Kapacitor MQTT Alert Documentation](https://docs.influxdata.com/kapacitor/v1/reference/event_handlers/mqtt/).
