# How to Configure Alerts in Time Series Analytics Microservice

This guide provides instructions for setting up alerts in **Time Series Analytics Microservice**.

## Publishing OPC-UA Alerts

To enable OPC-UA alerts in `Time Series Analytics Microservice`, please follow below steps.
The way to verify if the OPC-UA alerts are getting published would be check the `Time Series Analytics Microservice` logs OR
have any third-party OPC-UA client to connect to OPC-UA server to verify this.

1. Update the `config.json` file:
   ```json
   "alerts": {
       "opcua": {
           "opcua_server": "opc.tcp://ia-opcua-server:4840/freeopcua/server/",
           "namespace": 1,
           "node_id": 2004
       }
   }
   ```
### Configuring MQTT Alert in TICK Script

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

## Publishing MQTT Alerts

### MQTT Configuration in Time Series Analytics Microservice

To enable MQTT alerts, add the following configuration to `kapacitor_devmode.conf`:

```bash
[[mqtt]]
  enabled = true
  name = "my_mqtt_broker"
  default = true
  url = "tcp://ia-mqtt-broker:1883"
  username = ""
  password = ""
```

> **Note**: For external MQTT brokers with TLS, mount the required certificates to `/run/secrets/mqtt_certs` and update the `ssl-ca`, `ssl-cert`, and `ssl-key` paths in the configuration.

### Configuring MQTT Alert in TICK Script

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

To subscribe to MQTT alerts:

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

Identify the the MQTT broker pod name by running:
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

> **Note:**
> If you are deploying with the Edge Orchestrator, make sure to export the `KUBECONFIG` environment variable.


## Supporting Resources

- [Kapacitor MQTT Alert Documentation](https://docs.influxdata.com/kapacitor/v1/reference/event_handlers/mqtt/).
