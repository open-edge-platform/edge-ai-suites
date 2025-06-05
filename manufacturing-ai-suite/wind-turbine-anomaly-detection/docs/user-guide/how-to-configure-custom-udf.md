# How to Configure Time Series Analytics Microservice with Custom UDF deployment package

This guide provides instructions for setting up custom UDF deployment package (UDFs, TICKscripts, models) an config.json in **Time Series Analytics Microservice**.

- **`config.json`**:
   - Understand the configuration documented at [link](get-started.md#configjson) and update 
     as per the need to configure the custom UDF deployment package

- **`UDF Deployment package`**:

  1. **`udfs/`**:
    - Contains python scripts for UDFs.
    - If additional python packages are required, list them in `requirements.txt` using pinned versions.

  2. **`tick_scripts/`**:
    - Contains TICKscripts for data processing, analytics, and alerts.
    - Mode detail on writing TICKscript is available at <https://docs.influxdata.com/kapacitor/v1/reference/tick/introduction/>

    - Example TICKscript:
      
      ```bash
      dbrp "datain"."autogen"

      var data0 = stream
          |from()
              .database('datain')
              .retentionPolicy('autogen')
              .measurement('opcua')
          @windturbine_anomaly_detector()
          |alert()
              .crit(lambda: "anomaly_status" > 0)
              .message('Anomaly detected: Wind Speed: {{ index .Fields "wind_speed" }}, Grid Active Power: {{ index .Fields "grid_active_power" }}, Anomaly Status: {{ index .Fields "anomaly_status" }}')
              .mqtt('my_mqtt_broker')
              .topic('alerts/wind_turbine')
              .qos(1)
          |log()
              .level('INFO')
          |influxDBOut()
              .buffer(0)
              .database('datain')
              .measurement('opcua')
              .retentionPolicy('autogen')
      ```
    - Key sections:
      - **Input**: Fetch data from Telegraf (stream).
      - **Processing**: Apply UDFs for analytics.
      - **Alerts**: Configuration for publishing alerts (e.g., MQTT). Refer [link](#Publishing-mqtt-alerts)
      - **Logging**: Set log levels (`INFO`, `DEBUG`, `WARN`, `ERROR`).
      - **Output**: Publish processed data.

    For more details, refer to the [Kapacitor TICK Script Documentation](https://docs.influxdata.com/kapacitor/v1/reference/tick/introduction/).

  3. **`models/`**:
    - Contains model files (e.g., `.pkl`) used by UDF python scripts.


## With Volume Mounts

### Docker compose deployment

The files at `<path-to-edge-ai-suites-repo>/manufacturing-ai-suite/wind-turbine-anomaly-detection/time-series-analytics-microservice` representing the UDF deployment package (UDFs, TICKscripts, models)
and config.json has been volume mounted at `<path-to-edge-ai-suites-repo>/manufacturing-ai-suite/wind-turbine-anomaly-detection/docker-compose.yml`. If anything needs to be updated in the custom UDF deployment package and config.json, it has to be done at this location and the time series analytics microservice container
needs to be restarted.

### Helm deployment


