# Configure Alerts in Time Series Analytics Microservice

This section provides instructions for setting up alerts in **Time Series Analytics Microservice**.

## Docker Compose Deployment

### Docker - Publish MQTT Alerts

#### Configure MQTT Alerts

The following MQTT alerts are configured for both `Wind Turbine Anomaly Detection`
and `Weld Anomaly Detection` sample apps

<!--hide_directive
::::{tab-set}
:::{tab-item} hide_directive--> **Wind Turbine Anomaly Detection**
<!--hide_directive
:sync: tab1
hide_directive-->



[wind-turbine-anomaly-detection/time-series-analytics-config/config.json](
https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/config.json)

```json
  "alerts": {
      "mqtt": {
          "mqtt_broker_host": "ia-mqtt-broker",
          "mqtt_broker_port": 1883,
          "name": "my_mqtt_broker"
      }
   }
 ```

<!--hide_directive
:::
:::{tab-item} hide_directive--> **Weld Anomaly Detection**
<!--hide_directive
:sync: tab2
hide_directive-->

[weld-anomaly-detection/time-series-analytics-config/config.json](
https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/weld-anomaly-detection/time-series-analytics-config/config.json)

```json
  "alerts": {
      "mqtt": {
          "mqtt_broker_host": "ia-mqtt-broker",
          "mqtt_broker_port": 1883,
          "name": "my_mqtt_broker"
      }
   }
 ```

<!--hide_directive
:::
::::
hide_directive-->


#### Configure MQTT Alert in TICK Script

The following code snippets show how to add the MQTT, if not
already added, to `Wind Turbine Anomaly Detection` and `Weld Anomaly Detection`
sample apps. The TICK script has the following configuration done by default.

<!--hide_directive
::::{tab-set}
:::{tab-item} hide_directive-->**Wind Turbine Anomaly Detection**
<!--hide_directive
:sync: tab1
hide_directive-->


[wind-turbine-anomaly-detection/time-series-analytics-config/tick_scripts/windturbine_anomaly_detector.tick](
https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/tick_scripts/windturbine_anomaly_detector.tick)

```bash
data0
    |alert()
            .crit(lambda: "anomaly_status" > 0)
            .message('Anomaly detected for wind speed: {{ index .Fields "wind_speed" }} Grid Active Power: {{ index .Fields "grid_active_power" }}  Anomaly Status: {{ index .Fields "anomaly_status" }} ')
            .noRecoveries()
            .mqtt('my_mqtt_broker')
            .topic('alerts/wind_turbine')
            .qos(1)
```

<!--hide_directive

:::
:::{tab-item} hide_directive-->**Weld Anomaly Detection**

<!--hide_directive
:sync: tab2
hide_directive-->


[weld-anomaly-detection/time-series-analytics-config/tick_scripts/weld_anomaly_detector.tick](
https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/weld-anomaly-detection/time-series-analytics-config/tick_scripts/weld_anomaly_detector.tick)

```bash
data0
    |alert()
            .crit(lambda: "anomaly_status" > 0)
            .message('{"time": "{{ index .Time }}", "Pressure": {{ index .Fields "Pressure" }}, "CO2 Weld Flow": {{ index .Fields "CO2 Weld     Flow" }}, "anomaly_status": {{ index .Fields "anomaly_status" }} } ')
            .noRecoveries()
            .mqtt('my_mqtt_broker')
            .topic('alerts/weld_defects')
            .qos(1)
```

<!--hide_directive
:::
::::
hide_directive-->

> **Note:** Setting **QoS** to `1` ensures messages are delivered at least once.
> Alerts are preserved and re-sent if the MQTT broker reconnects after downtime.

### Docker - Subscribe to MQTT Alerts

Follow the steps to subscribe to the published MQTT alerts.

- To subscribe to all MQTT topics, execute the following command:

```sh
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t '#' -p 1883
```

- To subscribe to a specific MQTT topic, such as `alerts/wind_turbine`, use the following command.
  Note that the topic information can be found in the TICK Script.
  <!--hide_directive
  ::::{tab-set}
  :::{tab-item} hide_directive--> **Wind Turbine Anomaly Detection**
  <!--hide_directive
  :sync: tab1
  hide_directive-->

  [wind-turbine-anomaly-detection/time-series-analytics-config/tick_scripts/windturbine_anomaly_detector.tick](
  https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/tick_scripts/windturbine_anomaly_detector.tick)

  ```bash
  docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t alerts/wind_turbine -p 1883
  ```
  <!--hide_directive
  :::
  :::{tab-item} hide_directive--> **Weld Anomaly Detection**
  <!--hide_directive
  :sync: tab2
  hide_directive-->

  [weld-anomaly-detection/time-series-analytics-config/tick_scripts/weld_anomaly_detector.tick](
  https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/weld-anomaly-detection/time-series-analytics-config/tick_scripts/weld_anomaly_detector.tick)

  ```bash
  docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t alerts/weld_defects -p 1883
  ```

<!--hide_directive
:::
::::
hide_directive-->

### Docker - Publish OPC-UA Alerts

> **Note:**
> This section is applicable to Wind Turbine Anomaly Dectection sample app only.
> In other words, OPC UA alerts are not supported for Weld Anomaly Detection sample app.

#### Prerequisite

Ensure that `make up_opcua_ingestion` has been executed by following the steps
in the [getting started guide](../get-started.md#deploy-with-docker-compose) for the docker compose deployment

To enable OPC-UA alerts in `Time Series Analytics Microservice`, use the following steps.

#### Configuration

#### 1. Configure OPC-UA Alert in TICK Script

The following code snippets show how to add the OPC-UA alert, if not
already added, replace this in place of MQTT alert section in the TICK script.

<!--hide_directive
::::{tab-set}
:::{tab-item} hide_directive-->**Wind Turbine Anomaly Detection**
<!--hide_directive
:sync: tab1
hide_directive-->

[wind-turbine-anomaly-detection/time-series-analytics-config/tick_scripts/windturbine_anomaly_detector.tick](
https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/tick_scripts/windturbine_anomaly_detector.tick)

```bash
data0
    |alert()
        .crit(lambda: "anomaly_status" > 0)
        .message('Anomaly detected: Wind Speed: {{ index .Fields "wind_speed" }}, Grid Active Power: {{ index .Fields "grid_active_power" }}, Anomaly Status: {{ index .Fields "anomaly_status" }}')
        .noRecoveries()
        .post('http://localhost:5000/opcua_alerts')
        .timeout(30s)
```

<!--hide_directive
:::
:::{tab-item} hide_directive--> **Weld Anomaly Detection**
<!--hide_directive
:sync: tab2
hide_directive-->

[weld-anomaly-detection/time-series-analytics-config/tick_scripts/weld_anomaly_detector.tick](
https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/weld-anomaly-detection/time-series-analytics-config/tick_scripts/weld_anomaly_detector.tick)

```bash
data0
    |alert()
            .crit(lambda: "anomaly_status" > 0)
            .message('{"time": "{{ index .Time }}", "Pressure": {{ index .Fields "Pressure" }}, "CO2 Weld Flow": {{ index .Fields "CO2 Weld     Flow" }}, "anomaly_status": {{ index .Fields "anomaly_status" }} } ')
            .noRecoveries()
            .mqtt('my_mqtt_broker')
            .topic('alerts/weld_defects')
            .qos(1)
```

<!--hide_directive
:::
::::
hide_directive-->

> **Note:**
>
> - The `noRecoveries()` method suppresses recovery alerts, ensuring only critical alerts are sent.
> - If doing a Helm-based deployment on a Kubernetes cluster, after making changes to the TICKscript, copy the UDF deployment package using [step 4](../how-to-guides/how-to-deploy-with-helm.md#step-4--copy-the-udf-package-for-helm-deployment-to-time-series-analytics-microservice).

#### 2. Configuring OPC-UA Alert in config.json

Make the following REST API call to the Time Series Analytics microservice. Note that the
`mqtt` alerts key is replaced with the `opcua` key and its specific details:

<!--hide_directive
::::{tab-set}
:::{tab-item} hide_directive--> **Wind Turbine Anomaly Detection**
<!--hide_directive
:sync: tab1
hide_directive-->

[wind-turbine-anomaly-detection/time-series-analytics-config/config.json](
https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/config.json)

```sh
curl -k -X 'POST' \
'https://<HOST_IP>:3000/ts-api/config' \
-H 'accept: application/json' \
-H 'Content-Type: application/json' \
-d '{
    "udfs": {
        "name": "windturbine_anomaly_detector",
        "models": "windturbine_anomaly_detector.pkl",
        "device": "cpu"
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

<!--hide_directive
:::
:::{tab-item} hide_directive--> **Weld Anomaly Detection**
<!--hide_directive
:sync: tab2
hide_directive-->


[weld-anomaly-detection/time-series-analytics-config/config.json](
https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/weld-anomaly-detection/time-series-analytics-config/config.json)

```sh
curl -k -X 'POST' \
'https://<HOST_IP>:3000/ts-api/config' \
-H 'accept: application/json' \
-H 'Content-Type: application/json' \
-d '{
    "udfs": {
        "name": "weld_anomaly_detector",
        "models": "weld_anomaly_detector.cb"
    },
    "alerts": {
        "mqtt": {
            "mqtt_broker_host": "ia-mqtt-broker",
            "mqtt_broker_port": 1883,
            "name": "my_mqtt_broker"
        }
    }
}'
```

<!--hide_directive
:::
::::
hide_directive-->

### Docker - Subscribe to OPC UA Alerts using Sample OPCUA Subscriber

1. Install Python packages `asyncio` and `asyncua` to run the sample OPC UA subscriber

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

### Helm - Publish MQTT Alerts

For detailed instructions on configuring and publishing MQTT alerts, refer to the [Publish MQTT Alerts](#docker---publish-mqtt-alerts) section.

### Helm - Subscribe to MQTT Alerts

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

- To subscribe to MQTT topic such as `alerts/wind_turbine`, use the following command:

  <!--hide_directive
  ::::{tab-set}
  :::{tab-item} hide_directive--> **Wind Turbine Anomaly Detection**
  <!--hide_directive
  :sync: tab1
  hide_directive-->

  ```bash
  kubectl exec -it -n ts-sample-app <mqtt_broker_pod_name> -- mosquitto_sub -h localhost -v -t alerts/wind_turbine -p 1883
  ```

  <!--hide_directive
  :::
  :::{tab-item} hide_directive--> **Weld Anomaly Detection**
  <!--hide_directive
  :sync: tab2
  hide_directive-->

  ```bash
  kubectl exec -it -n ts-sample-app <mqtt_broker_pod_name> -- mosquitto_sub -h localhost -v -t alerts/weld_defects -p 1883
  ```

<!--hide_directive
:::
::::
hide_directive-->

### Helm - Publish OPC-UA Alerts

> **Note:**
>
> Ensure a sample app is deployed by following the [installation step](../how-to-guides/how-to-deploy-with-helm.md#step-3-install-helm-charts) for OPC-UA ingestion.

To enable OPC-UA alerts in `Time Series Analytics Microservice`, please follow below steps.

### **Configuration**

1. Configuring OPC-UA Alert in TICK Script

   Configure the TICK script by following [these instructions](#1-configure-opc-ua-alert-in-tick-script).

2. Copying the TICK Script

   Copy the TICK script using the following commands:

   <!--hide_directive
   ::::{tab-set}
   :::{tab-item} hide_directive--> **Wind Turbine Anomaly Detection**
   <!--hide_directive
   :sync: tab1
   hide_directive-->

   ```sh
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection # path relative to git  clone   folder
   cd time-series-analytics-config
   export SAMPLE_APP="wind-turbine-anomaly-detection"
   mkdir -p $SAMPLE_APP
   cp -r models tick_scripts udfs $SAMPLE_APP/.

   POD_NAME=$(kubectl get pods -n ts-sample-app -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep    deployment-time-series-analytics-microservice | head -n 1)

   kubectl cp $SAMPLE_APP $POD_NAME:/tmp/ -n ts-sample-app
   ```

  <!--hide_directive
  :::{tab-set}
  :::{tab-item} hide_directive--> **Weld Anomaly Detection**
  <!--hide_directive
  :sync: tab2
  hide_directive-->

   ```sh
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/weld-anomaly-detection # path relative to git clone   folder
   cd time-series-analytics-config
   export SAMPLE_APP="weld-anomaly-detection"
   mkdir -p $SAMPLE_APP
   cp -r models tick_scripts udfs $SAMPLE_APP/.

   POD_NAME=$(kubectl get pods -n ts-sample-app -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep    deployment-time-series-analytics-microservice | head -n 1)

   kubectl cp $SAMPLE_APP $POD_NAME:/tmp/ -n ts-sample-app
   ```

  <!--hide_directive
  :::
  ::::
  hide_directive-->

3. Configuring OPC-UA Alert in `config.json`

   Make the following REST API call to the Time Series Analytics microservice. Note that the `mqtt` alerts key is replaced with the `opcua` key and its specific details:

   <!--hide_directive
   ::::{tab-set}
   :::{tab-item} hide_directive--> **Wind Turbine Anomaly Detection**
   <!--hide_directive
   :sync: tab1
   hide_directive-->

   [wind-turbine-anomaly-detection/time-series-analytics-config/config.json](
   https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/config.json)

   ```sh
   curl -k -X 'POST' \
   'https://<HOST_IP>:30001/ts-api/config' \
   -H 'accept: application/json' \
   -H 'Content-Type: application/json' \
   -d '{
       "udfs": {
           "name": "windturbine_anomaly_detector",
           "models": "windturbine_anomaly_detector.pkl",
           "device": "cpu"
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

   <!--hide_directive
   :::
   :::{tab-item} hide_directive--> **Weld Anomaly Detection**
   <!--hide_directive
   :sync: tab2
   hide_directive-->

   [weld-anomaly-detection/time-series-analytics-config/config.json](
   https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/weld-anomaly-detection/time-series-analytics-config/config.json)

   ```sh
   curl -k -X 'POST' \
   'https://<HOST_IP>:30001/ts-api/config' \
   -H 'accept: application/json' \
   -H 'Content-Type: application/json' \
   -d '{
       "udfs": {
           "name": "weld_anomaly_detector",
           "models": "weld_anomaly_detector.pkl",
           "device": "cpu"
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

   <!--hide_directive
  :::
  ::::
  hide_directive-->

### Helm - Subscribe to OPC UA Alerts using Sample OPCUA Subscriber

To subscribe to OPC-UA alerts, follow [these steps](#docker---subscribe-to-opc-ua-alerts-using-sample-opcua-subscriber).

## Supporting Resources

- [Kapacitor MQTT Alert Documentation](https://docs.influxdata.com/kapacitor/v1/reference/event_handlers/mqtt/).
