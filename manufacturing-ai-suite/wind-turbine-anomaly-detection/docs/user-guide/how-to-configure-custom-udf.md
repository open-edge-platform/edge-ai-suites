# How to Configure Time Series Analytics Microservice with Custom UDF

This guide provides instructions for setting up custom User-Defined Functions (UDFs) in **Time Series Analytics Microservice**.

## Using Custom UDFs with Volume Mounts

To use custom UDFs with the Time Series Analytics Microservice, ensure the following directory structure is in place:

```
time_series_analytics_microservice
├── docker-compose.yml
├── config
│   ├── kapacitor_devmode.conf
│   ├── kapacitor.conf
├── udfs
│   ├── requirements.txt
│   ├── <udf_script.py>
├── tick_scripts
│   ├── <tick_script.tick>
├── models
    ├── <model_file.pkl>
```

## Directory Details

1. **`config/`**:
   - Contains Kapacitor configuration files:
     - `kapacitor_devmode.conf`
   - Update the `udf` section in above file to include the task name and UDF script name:

     ```bash
     [udf]
     # Configuration for UDFs (User Defined Functions)
     [udf.functions]
         [udf.functions.<task_name>]
         prog = "python3"
         args = ["-u", "/app/udfs/<udf_script.py>"]
         timeout = "60s"
         [udf.functions.<task_name>.env]
             PYTHONPATH = "/app/kapacitor_python/:/tmp/py_package"
     ```

2. **`udfs/`**:
   - Contains Python scripts for UDFs.
   - If additional Python packages are required, list them in `requirements.txt` using pinned versions.

3. **`tick_scripts/`**:
   - Contains TICK scripts for data processing, analytics, and alerts.
   - Example TICK script:
     
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
     - **Alerts**: Configuration for publishing alerts (e.g., MQTT). Refer [link](how-to-configure-alerts.md#publishing-mqtt-alerts)
     - **Logging**: Set log levels (`INFO`, `DEBUG`, `WARN`, `ERROR`).
     - **Output**: Publish processed data.

   For more details, refer to the [Kapacitor TICK Script Documentation](https://docs.influxdata.com/kapacitor/v1/reference/tick/introduction/).

4. **`models/`**:
   - Contains model files (e.g., `.pkl`) used by UDF scripts.
