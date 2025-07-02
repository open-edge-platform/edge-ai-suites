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

> **Note**: Follow the [getting started](./get-started.md) to have the Wind Turbine Anomaly Detection sample app deployed

### Docker compose deployment Only

The files at `edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/time_series_analytics_microservice` representing the UDF deployment package (UDFs, TICKscripts, models)
and config.json has been volume mounted for the Time Series Analytics Microservice service in `edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/docker-compose.yml`. If anything needs to be updated in the custom UDF deployment package and config.json, it has to be done at this location and the time series analytics microservice container needs to be restarted manually.

## With Model Registry

> **Note**:
> 1. If doing docker based deployment, ensure the Wind Turbine Anomaly Detection sample app is deployed by following [getting started](./get-started.md)
> 2. If doing Helm based deployment on Kubernetes cluster, ensure the Wind Turbine Anomaly Detection sample app is deployed by following [how to deploy with helm](./how-to-deploy-with-helm.md)

This approach facilitates the updates to `Time Series Analytics` microservice at runtime by updating the configuration and UDF deployment
package using its REST APIs.

### 1. UDF Deployment Package structure

If one wants to create a separate UDF deployment package, just ensure to have the following structure
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

### 2. Uploading Models to the Model Registry

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

### 3. Updating Time Series Analytics Microservice config for Model Registry usage


1. Run the below command, to update the configuration in `Time Series Analytics` microservice. 
   Please note, the default of `<PORT>` value is `5000` for docker compose deployment and `30002` for helm based deployment.

    ```bash
    curl -X 'POST' \
    'http://<HOST_IP>:<PORT>/config' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/json' \
    -d '{
        "model_registry": {
            "enable": true,
            "version": "1.0"
        },
        "udfs": {
            "name": "windturbine_anomaly_detector",
            "models": "windturbine_anomaly_detector.pkl"
        },
        "alerts": {
            "mqtt": {
                "mqtt_broker_host": "ia-mqtt-broker",
                "mqtt_broker_port": 1883,
                "name": "my_mqtt_broker"
            }
        }
    }
    '
    ```

For more details, please refer `Time Series Analytics` microservice API docs [here](./how-to-update-config.md#how-to-update-config-in-time-series-analytics-microservice).
