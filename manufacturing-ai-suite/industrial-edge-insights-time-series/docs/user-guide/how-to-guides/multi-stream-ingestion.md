# Enable Multi-Stream Ingestion

This guide explains how to enable multi-stream ingestion for Time Series Analytics sample apps.
Multi-stream ingestion processes multiple streams in parallel to improve throughput and scale testing.

## Parameter Reference

Use `num_of_streams` in the deployment command:

- `num_of_streams=<NUMBER_OF_STREAMS>`: Number of parallel ingestion streams.
- Example: `num_of_streams=3` starts three concurrent streams.

> **Note:**
>
> - If `num_of_streams` is not provided, the default value is `1`.
> - `up_opcua_ingestion` is supported only for the `wind-turbine-anomaly-detection` sample app.

## Deploy with Docker Compose

Run one of the following commands based on your sample app and ingestion mode.

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Wind Turbine Anomaly Detection**
<!--hide_directive:sync: tab1hide_directive-->

```bash
# Deploy with OPC-UA multi-stream ingestion
export OPCUA_SERVER_PORT_MAPPING=30003-30100
make up_opcua_ingestion app="wind-turbine-anomaly-detection" num_of_streams=<NUMBER_OF_STREAMS>

# Deploy with MQTT multi-stream ingestion
make up_mqtt_ingestion app="wind-turbine-anomaly-detection" num_of_streams=<NUMBER_OF_STREAMS>
```

<!--hide_directive:::
:::{tab-item}hide_directive--> **Weld Defect Detection**
<!--hide_directive:sync: tab2hide_directive-->

```bash
# Deploy with MQTT multi-stream ingestion
make up_mqtt_ingestion app="weld-defect-detection" num_of_streams=<NUMBER_OF_STREAMS>
```

<!--hide_directive:::
::::hide_directive-->

## Verification

After deployment, verify service status:

```bash
make status
```