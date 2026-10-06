# Configure Alerts

This section provides instructions for setting up alerts in **Time Series Analytics Microservice**.

## Docker Compose Deployment

### Docker - Publish MQTT Alerts

#### Configure MQTT Alerts

The following MQTT alerts are configured for both `Wind Turbine Anomaly Detection` sample app. Refer to the `alerts` section of each app's `config.json`:

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Wind Turbine Anomaly Detection**
<!--hide_directive:sync: tab1hide_directive-->

[wind-turbine-anomaly-detection/time-series-analytics-config/config.json](
https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/config.json)


<!--hide_directive:::
::::hide_directive-->

#### Configure MQTT Alert in the Core plugin

The Core plugin publishes anomaly alerts to `alerts/wind_turbine` when the
`mqtt` section is present in the app configuration. The broker host and port
are read from `config.json`; no TICKscript edit is needed.

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Wind Turbine Anomaly Detection**
<!--hide_directive:sync: tab1hide_directive-->

[wind-turbine-anomaly-detection/time-series-analytics-config/udfs/influx3_windturbine/__init__.py](
https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/udfs/influx3_windturbine/__init__.py)


<!--hide_directive:::
::::hide_directive-->

> [!NOTE]
> Setting **QoS** to `1` ensures messages are delivered at least once.
> Alerts are preserved and re-sent if the MQTT broker reconnects after downtime.

### Docker - Subscribe to MQTT Alerts

Follow the steps to subscribe to the published MQTT alerts.

- To subscribe to all MQTT topics, execute the following command:

```sh
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t '#' -p 1883
```

- To subscribe to `alerts/wind_turbine`, use the following command.

  <!--hide_directive::::{tab-set}
  :::{tab-item}hide_directive--> **Wind Turbine Anomaly Detection**
  <!--hide_directive:sync: tab1hide_directive-->

  [wind-turbine-anomaly-detection/time-series-analytics-config/udfs/influx3_windturbine/__init__.py](
  https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/udfs/influx3_windturbine/__init__.py)

  ```bash
  docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t alerts/wind_turbine -p 1883
  ```

  <!--hide_directive:::
  ::::hide_directive-->

### Docker - Publish OPC-UA Alerts

#### Prerequisite

Ensure that `make up_opcua_ingestion` has been executed by following the steps
in the [getting started guide](../get-started.md#deploy-with-docker-compose) for the docker compose deployment

To enable OPC-UA alerts in `Time Series Analytics Microservice`, use the following steps.

#### Configuration

#### 1. Configure OPC-UA Alert in the app config

Select OPC-UA alerts by posting `config-opcua.json`. The Core plugin forwards
anomaly messages to the existing `/opcua_alerts` API; no TICKscript edit is needed.

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Wind Turbine Anomaly Detection**
<!--hide_directive:sync: tab1hide_directive-->

[wind-turbine-anomaly-detection/time-series-analytics-config/config-opcua.json](
https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/config-opcua.json)

#### 2. Upload the new UDF deployment package

To upload the Core UDF package, run the following commands:

```bash
cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection # path relative to git  clone   folder
cd time-series-analytics-config
export SAMPLE_APP="wind-turbine-anomaly-detection"

rm -f ${SAMPLE_APP}.tar
tar --exclude='__pycache__' --exclude='*.pyc' -cf ${SAMPLE_APP}.tar models/ udfs/influx3_windturbine/
curl -X POST https://localhost:3000/ts-api/udfs/package -F "file=@${SAMPLE_APP}.tar" -k
```

> [!NOTE]
> If the `curl` command fails with `502`, wait briefly and retry the command. This response can occur while the Time Series Analytics Microservice is still becoming ready.

#### 3. Configuring OPC-UA Alert in config.json

Make the following REST API call to the Time Series Analytics microservice using
[`config-opcua.json`](https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/config-opcua.json),
which replaces the `mqtt` alerts key from `config.json` with the `opcua` key and its specific details:

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Wind Turbine Anomaly Detection**
<!--hide_directive:sync: tab1hide_directive-->

[wind-turbine-anomaly-detection/time-series-analytics-config/config.json](
https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/config.json)

```sh
cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config
curl -k -X 'POST' \
'https://localhost:3000/ts-api/config' \
-H 'accept: application/json' \
-H 'Content-Type: application/json' \
-d @config-opcua.json
```

### Docker - Subscribe to OPC UA Alerts using Sample OPCUA Subscriber

1. Install Python packages `asyncio` and `asyncua` to run the sample OPC UA subscriber

   ```bash
   python3 -m venv venv
   source venv/bin/activate
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

  <!--hide_directive::::{tab-set}
  :::{tab-item}hide_directive--> **Wind Turbine Anomaly Detection**
  <!--hide_directive:sync: tab1hide_directive-->

  ```bash
  kubectl exec -it -n ts-sample-app <mqtt_broker_pod_name> -- mosquitto_sub -h localhost -v -t alerts/wind_turbine -p 1883
  ```


  <!--hide_directive:::
  ::::hide_directive-->

### Helm - Publish OPC-UA Alerts

> [!NOTE]
>
> Ensure a sample app is deployed by following the [installation step](../get-started/deploy-with-helm.md#step-3-install-helm-charts) for OPC-UA ingestion.

To enable OPC-UA alerts in `Time Series Analytics Microservice`, please follow below steps.

### **Configuration**

1. Configuring OPC-UA Alert in TICK Script

   Configure the TICK script by following [these instructions](#1-configure-opc-ua-alert-in-tick-script).

2. Copying the TICK Script

   Copy the TICK script using the following commands:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Wind Turbine Anomaly Detection**
   <!--hide_directive:sync: tab1hide_directive-->

   ```sh
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection # path relative to git  clone   folder
   cd time-series-analytics-config
   export SAMPLE_APP="wind-turbine-anomaly-detection"
   rm -f ${SAMPLE_APP}.tar
   tar cf ${SAMPLE_APP}.tar models/ tick_scripts/ udfs/

   curl -X POST https://localhost:30001/ts-api/udfs/package -F "file=@${SAMPLE_APP}.tar" -k
   ```

    > [!NOTE]
    > If the `curl` command fails with `502`, wait briefly and retry the command. This response can occur while the Time Series Analytics Microservice is still becoming ready.

3. Configuring OPC-UA Alert in `config.json`

   Make the following REST API call to the Time Series Analytics microservice using
   [`config-opcua.json`](https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/config-opcua.json),
   which replaces the `mqtt` alerts key from `config.json` with the `opcua` key and its specific details:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Wind Turbine Anomaly Detection**
   <!--hide_directive:sync: tab1hide_directive-->

   [wind-turbine-anomaly-detection/time-series-analytics-config/config.json](
   https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/config.json)

   ```sh
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config
   curl -k -X 'POST' \
   'https://localhost:30001/ts-api/config' \
   -H 'accept: application/json' \
   -H 'Content-Type: application/json' \
   -d @config-opcua.json
   ```

### Helm - Subscribe to OPC UA Alerts using Sample OPCUA Subscriber

To subscribe to OPC-UA alerts, follow [these steps](#docker---subscribe-to-opc-ua-alerts-using-sample-opcua-subscriber).

## Supporting Resources

- [Core Processing Engine documentation](https://docs.influxdata.com/influxdb3/core/plugins/).
