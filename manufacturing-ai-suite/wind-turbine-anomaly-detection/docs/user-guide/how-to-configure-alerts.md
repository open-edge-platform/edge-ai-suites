# How to Configure Alerts in Time Series Analytics Microservice

This guide provides instructions for setting up alerts in **Time Series Analytics Microservice**.
Please note the `edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/time_series_analytics_microservice/config.json` changes would be auto-picked in the docker compose deployment but for helm deployment once the alerts configuration changes are done as below, please regenerate the helm charts and install by following steps mentioned at [link](how-to-deploy-with-helm.md)

## Publishing MQTT Alerts

### Configurating MQTT Alerts

By default, the below MQTT alerts is configured in `edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/time_series_analytics_microservice/config.json` file.

  ```json
    "alerts": {
        "mqtt": {
            "mqtt_broker_host": "ia-mqtt-broker",
            "mqtt_broker_port": 1883,
            "name": "my_mqtt_broker"
        }
     }
   ```

### Configuring MQTT Alert in TICK Script

The details below shows the snippet on how to add the MQTT if not 
already added. By default, the `edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/time_series_analytics_microservice/tick_scripts/windturbine_anomaly_detector.tick` TICK Script has the below configuration done by default.

```bash
@windturbine_anomaly_detector()
|alert()
    .crit(lambda: "anomaly_status" > 0)
    .message('Anomaly detected: Wind Speed: {{ index .Fields "wind_speed" }}, Grid Active Power: {{ index .Fields "grid_active_power" }}, Anomaly Status: {{ index .Fields "anomaly_status" }}')
    .mqtt('my_mqtt_broker')
    .topic('alerts/wind_turbine')
    .qos(1)
```

> **Note**: Setting **QoS** to `1` ensures messages are delivered at least once. Alerts are preserved and resent if the MQTT broker reconnects after downtime.

### Subscribing to MQTT Alerts

To subscribe to the published MQTT alerts:

#### Docker compose deployment

To subscribe to all MQTT topics, execute the following command:

```sh
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t '#' -p 1883
```

To subscribe to a specific MQTT topic, such as `alerts/wind_turbine`, use the following command. Note that the topic information can be found in the TICKScript:

```sh
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t alerts/wind_turbine -p 1883
```

#### Helm deployment

To subscribe to MQTT topics in a Helm deployment, execute the following command:

Identify the MQTT broker pod name by running:
```sh
kubectl get pods -n apps | grep mqtt-broker
```

Use the pod name from the output of the above command to subscribe to all topics:
```sh
kubectl exec -it -n apps <mqtt_broker_pod_name> -- mosquitto_sub -h localhost -v -t '#' -p 1883
```

To subscribe to the `alerts/wind_turbine` topic, use the following command:

```sh
kubectl exec -it -n apps <mqtt_broker_pod_name> -- mosquitto_sub -h localhost -v -t alerts/wind_turbine -p 1883
```

## Publishing OPC-UA Alerts

### Prerequisite

Please ensure that `make up_opcua_ingestion` has been executed by following the steps
in the [getting started guide](./get-started.md#deploy-with-docker-compose)

To enable OPC-UA alerts in `Time Series Analytics Microservice`, please follow below steps.
You can verify the publishing of OPC-UA alerts by checking the logs of the `Time Series Analytics Microservice`.

### Configuration

### 1. Configuring OPC-UA Alert in TICK Script

The details below shows the snippet on how to add the OPC-UA alert if not 
already added, please replace this in place of MQTT alert section at
`edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/time_series_analytics_microservice/tick_scripts/windturbine_anomaly_detector.tick`.

```bash
data0
    |alert()
        .crit(lambda: "anomaly_status" > 0)
        .message('Anomaly detected: Wind Speed: {{ index .Fields "wind_speed" }}, Grid Active Power: {{ index .Fields "grid_active_power" }}, Anomaly Status: {{ index .Fields "anomaly_status" }}')
        .noRecoveries()
        .post('http://localhost:5000/opcua_alerts')
        .timeout(30s)
```
> **Note**:
> - The `noRecoveries()` method suppresses recovery alerts, ensuring only critical alerts are sent.
> - If doing a Helm-based deployment on a Kubernetes cluster, after making changes to the tick script, copy the UDF deployment package using [step](./how-to-deploy-with-helm.md#copy-the-windturbine_anomaly_detection-udf-package-for-helm-deployment-to-time-series-analytics-microservice).

### 2. Configuring OPC-UA Alert in config.json

Update the Time Series Analytics Microservice `edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/time_series_analytics_microservice/config.json` to add the following `opcua` details to the `alerts` section by following the [steps to update config](./how-to-update-config.md#how-to-update-config-in-time-series-analytics-microservice).

   ```json
   "alerts": {
       "opcua": {
           "opcua_server": "opc.tcp://ia-opcua-server:4840/freeopcua/server/",
           "namespace": 1,
           "node_id": 2004
       }
   }
   ```


### Subscribing to OPC UA Alerts using Sample OPCUA Subscriber

1. Expose the port `4840` of `ia-opcua-server` service in `docker-compose.yml` under `edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/docker-compose.yml#L183` as below

    ```yaml
    ia-opcua-server:
    ...
    ports:
    - "4840:4840"
    ```

2. Deploy the Sample App using below commands
    ```bash
    cd edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection
    make up_opcua_ingestion
    ```

3. Install python packages `asyncio` and `asyncua` to run the sample opc ua subscriber 
    ```bash
    pip install asyncio asyncua
    ```

4. Run the following sample OPC UA subscriber by updating the `<IP-Address of OPCUA Server>` to read the alerts published to server on tag `ns=1;i=2004` from Time Series Analytics Microservice.
    ```python
    import asyncio
    from asyncua import Client, Node
    class SubscriptionHandler:
        def datachange_notification(self, node: Node, val, data):
            print(val)
    async def main():
        client = Client(url="opc.tcp://<IP-Address of OPCUA Server>:4840/freeopcua/server/")
        async with client:
            handler = SubscriptionHandler()
            subscription = await client.create_subscription(50, handler)
            myvarnode = client.get_node("ns=1;i=2004")
            await subscription.subscribe_data_change(myvarnode)
            await asyncio.sleep(100)
            await subscription.delete()
            await asyncio.sleep(1)
    if __name__ == "__main__":
        asyncio.run(main())
    ```

## Supporting Resources

- [Kapacitor MQTT Alert Documentation](https://docs.influxdata.com/kapacitor/v1/reference/event_handlers/mqtt/).
