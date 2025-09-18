# Configure Alerts in Time Series Analytics Microservice

This section provides instructions for setting up alerts in **Time Series Analytics Microservice**.

## Docker Compose Deployment

### Publish MQTT Alerts

#### Configure MQTT Alerts

By default, the following MQTT alerts is configured in `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/config.json` file.

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
already added. By default, the `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/tick_scripts/windturbine_anomaly_detector.tick` TICK Script has the following configuration done by default.

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

Follow the steps to subscribe to the published MQTT alerts.

- To subscribe to all MQTT topics, execute the following command:

```sh
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t '#' -p 1883
```

- To subscribe to a specific MQTT topic, such as `alerts/wind_turbine`, use the following command. Note that the topic information can be found in the TICKScript:

```sh
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t alerts/wind_turbine -p 1883
```

### Publishing OPC-UA Alerts

#### Prerequisite

Ensure that `make up_opcua_ingestion` has been executed by following the steps
in the [getting started guide](./get-started.md#deploy-with-docker-compose) for the docker compose deployment

To enable OPC-UA alerts in `Time Series Analytics Microservice`, use the following steps.

#### Configuration

#### 1. Configure OPC-UA Alert in TICK Script

The following details shows the snippet on how to add the OPC-UA alert if not 
already added, replace this in place of MQTT alert section at
`edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/tick_scripts/windturbine_anomaly_detector.tick`.

```bash
data0
    |alert()
        .crit(lambda: "anomaly_status" > 0)
        .message('Anomaly detected: Wind Speed: {{ index .Fields "wind_speed" }}, Grid Active Power: {{ index .Fields "grid_active_power" }}, Anomaly Status: {{ index .Fields "anomaly_status" }}')
        .noRecoveries()
        .post('https://localhost:3000/ts-api/opcua_alerts')
        .timeout(30s)
```
> **Note**:
> - The `noRecoveries()` method suppresses recovery alerts, ensuring only critical alerts are sent.
> - If doing a Helm-based deployment on a Kubernetes cluster, after making changes to the tick script, copy the UDF deployment package using [step](./how-to-deploy-with-helm.md#copy-the-windturbine_anomaly_detection-udf-package-for-helm-deployment-to-time-series-analytics-microservice).

#### 2. Configuring OPC-UA Alert in config.json

Make the following REST API call to the Time Series Analytics microservice. Note that the `mqtt` alerts key is replaced with the `opcua` key and its specific details:

```sh
curl -X 'POST' \
'https://<HOST_IP>:3000/ts-api/config' \
-H 'accept: application/json' \
-H 'Content-Type: application/json' \
-d '{
    "model_registry": {
        "enable": false,
        "version": "1.0"
    },
    "udfs": {
        "name": "windturbine_anomaly_detector",
        "models": "windturbine_anomaly_detector.pkl"
    },
    "alerts": {
        "opcua": {
            "opcua_server": "opc.tcp://ia-opcua-server:4840/freeopcua/server/",
            "namespace": 1,
            "node_id": 2004
        }
    }
}'
```

#### Subscribe to OPC UA Alerts using Sample OPCUA Subscriber

1. Install python packages `asyncio` and `asyncua` to run the sample opc ua subscriber 
    ```bash
    pip install asyncio asyncua
    ```

2. Run the following sample OPC UA subscriber by updating the `<IP-Address of OPCUA Server>` to read the alerts published to server on tag `ns=1;i=2004` from Time Series Analytics Microservice.

    ```python
    import asyncio
    from asyncua import Client, Node
    class SubscriptionHandler:
        def datachange_notification(self, node: Node, val, data):
            print(val)
    async def main():
        client = Client(url="opc.tcp://<IP-Address of OPCUA Server>:30003/freeopcua/server/")
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

## Helm Deployment

- **Publish MQTT Alerts**

For detailed instructions on configuring and publishing MQTT alerts, refer to the [Publish MQTT Alerts](#publish-mqtt-alerts) section.

- **Subscribe to MQTT Alerts**

Follow the steps to subscribe to the published MQTT alerts.

To subscribe to MQTT topics in a Helm deployment, execute the following command:

- Identify the MQTT broker pod name by running:

```sh
kubectl get pods -n ts-sample-app | grep mqtt-broker
```

- Use the pod name from the output of the above command to subscribe to all topics:
```sh
kubectl exec -it -n ts-sample-app <mqtt_broker_pod_name> -- mosquitto_sub -h localhost -v -t '#' -p 1883
```

- To subscribe to the `alerts/wind_turbine` topic, use the following command:

```sh
kubectl exec -it -n ts-sample-app <mqtt_broker_pod_name> -- mosquitto_sub -h localhost -v -t alerts/wind_turbine -p 1883
```

- **Publish OPC-UA Alerts**


> **Note:**
> Ensure the Wind Turbine Anomaly Detection sample app is deployed using the [installation step](./how-to-deploy-with-helm.md#install-helm-charts---use-only-one-of-the-options-below) for OPC-UA ingestion.

To enable OPC-UA alerts in `Time Series Analytics Microservice`, please follow below steps.

- Configuration

1. Configuring OPC-UA Alert in TICK Script

Configure the tick script by following [these instructions](#1-configure-opc-ua-alert-in-tick-script).

2. Copying the TICK script

Copy the TICK script using the following command:

```sh
cd edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection # path relative to git clone folder
cd time-series-analytics-config
mkdir -p windturbine_anomaly_detector
cp -r models tick_scripts udfs windturbine_anomaly_detector/.

POD_NAME=$(kubectl get pods -n ts-sample-app -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-time-series-analytics-microservice | head -n 1)

kubectl cp windturbine_anomaly_detector $POD_NAME:/tmp/ -n ts-sample-app
```

3. Configuring OPC-UA Alert in config.json

Make the following REST API call to the Time Series Analytics microservice. Note that the `mqtt` alerts key is replaced with the `opcua` key and its specific details:

```sh
curl -X 'POST' \
'http://<HOST_IP>:30002/config' \
-H 'accept: application/json' \
-H 'Content-Type: application/json' \
-d '{
    "model_registry": {
        "enable": false,
        "version": "1.0"
    },
    "udfs": {
        "name": "windturbine_anomaly_detector",
        "models": "windturbine_anomaly_detector.pkl"
    },
    "alerts": {
        "opcua": {
            "opcua_server": "opc.tcp://ia-opcua-server:4840/freeopcua/server/",
            "namespace": 1,
            "node_id": 2004
        }
    }
}'
```

- **Subscribe to OPC UA Alerts using Sample OPCUA Subscriber**

To subscribe to OPC-UA alerts, follow [these steps](#subscribe-to-opc-ua-alerts-using-sample-opcua-subscriber).

## Supporting Resources

- [Kapacitor MQTT Alert Documentation](https://docs.influxdata.com/kapacitor/v1/reference/event_handlers/mqtt/).
