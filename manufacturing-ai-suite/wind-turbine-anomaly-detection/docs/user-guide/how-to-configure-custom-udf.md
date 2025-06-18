# How to Configure Time Series Analytics Microservice with Custom UDF deployment package

This guide provides instructions for setting up custom UDF deployment package (UDFs, TICKscripts, models) and config.json in **Time Series Analytics Microservice**.

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

The files at `edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/time_series_analytics_microservice` representing the UDF deployment package (UDFs, TICKscripts, models)
and config.json has been volume mounted at `edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/docker-compose.yml`. If anything needs to be updated in the custom UDF deployment package and config.json, it has to be done at this location and the time series analytics microservice container needs to be restarted.

## With Model Registry

### Uploading Models to the Model Registry

Below steps show how to create and upload the wind turbine anomaly detection UDF deployment package
to the Model Registry microservice.

1. The following step demonstrates how to create a sample model file from an existing model folder for uploading to the Model Registry. If you already have a model zip file, you can skip this step.
   ```bash
   cd edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/time_series_analytics_microservice/
   zip -r windturbine_anomaly_detector.zip udfs models tick_scripts
   ```
   You can utilize the generated `windturbine_anomaly_detector.zip` absolute path as `<udf_deployment_package_path.zip>` in the next step

2. Upload a model file to Model Registry
    ```bash
   curl -L -X POST "http://<HOST_IP>:32002/models" \
   -H 'Content-Type: multipart/form-data' \
   -F 'name="windturbine_anomaly_detector"' \
   -F 'version="1.0"' \
   -F 'file=@<udf_deployment_package_path.zip>;type=application/zip'
    ```

### UDF Deployment Package structure

If one wants to create a separate deployment package, just ensure to have the following structure
before zipping and uploading it to Model Registry.

> **NOTE**: Please ensure to have the same name for udf python script, TICK script and model name.

```
udfs/
    ├── requirements.txt
    ├── <name.py>
tick_scripts/
    ├── <name.tick>
models/
    ├── <name.pkl>
```


### Updating Time Series Analytics Microservice `config.json` for Model Registry usage

#### Docker compose deployment

To fetch UDFs and models from the Model Registry, update the configuration file at:
`edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/time_series_analytics_microservice/config.json`.

1. Set `fetch_from_model_registry` to `true`.
2. Specify the `task_name` and `version` as defined in the Model Registry.
   
   > **Note**: Mismatched task names or versions will cause the microservice to restart.
4. Update the `tick_script` and `udfs` sections with the appropriate `name` and `models` details.

As we are watching on `config.json` changes, the `ia-time-series-analytics-microservice` would auto-restart.

#### Helm deployment

Follow the below steps:
1. Configure `edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/time_series_analytics_microservice/config.json` as per [above steps](#docker-compose-deployment)
2. Run below command to generate the helm charts
   ```bash
   cd edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection # path relative to git clone folder
   make gen_helm_charts
   ```
3. Follow helm configuration and deployment steps at [link](./how-to-deploy-with-helm.md)
