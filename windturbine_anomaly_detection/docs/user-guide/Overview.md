# Predictive Maintenance - Wind Turbine Anomaly Detection Sample App

In the Energy Sector, such as wind turbines for power generation, unexpected equipment failures result in costly downtime and operational inefficiencies. Using AI-driven predictive analytics, edge devices can monitor equipment health through sensor data (e.g. power generation and wind speed), detect anomalous trends indicative of wear or failure, and alert operators to schedule maintenance proactively. This enhances productivity, reduces costs, and extends equipment lifespan.

This sample application demonstrates a time series use case by detecting the anomalous power generation patterns relative to wind speed. By identifying deviations, it helps optimize maintenance schedules and prevent potential turbine failures, enhancing operational efficiency. 

## How it works

- **Data Sources**: Using the `simulator/simulation_data/windturbine_data.csv` which is a normalized version of open source data wind turbine dataset from <https://www.kaggle.com/datasets/berkerisen/wind-turbine-scada-dataset>.
  This data is being ingested into **Telegraf** using either the **OPC-UA** OR **MQTT** protocol using our **OPC-UA** server OR **MQTT** publisher respectively.
  
- **Data Ingestion**: **Telegraf** through its input plugins (**OPC-UA** OR **MQTT**) gathers the data and sends this input data to both **InfluxDB** and **Time Series Analytics Microservice**.

- **Data Storage**: **InfluxDB** stores the incoming data coming from **Telegraf**.

- **Data Processing**: **Time Series Analytics Microservice** uses the User Defined Function(UDF) deployment package(TICK Scripts, UDFs, Models) which is already built-in to the container image. The UDF deployment package is available
at `time_series_analytics_microservice`. Directory details is as below:
  
   1. **`config.json`**:
      The `task` section defines the settings for the Kapacitor task and User-Defined Functions (UDFs).

      | Key                     | Description                                                                                     | Example Value                          |
      |-------------------------|-------------------------------------------------------------------------------------------------|----------------------------------------|
      | `fetch_from_model_registry` | Boolean flag to enable fetching UDFs and models from the Model Registry.                     | `true` or `false`                      |
      | `version`               | Specifies the version of the task or model to use.                                             | `"1.0"`                                |
      | `tick_script`           | The name of the TICK script file used for data processing and analytics.                        | `"windturbine_anomaly_detector.tick"`  |
      | `task_name`             | The name of the Kapacitor task.                                                                | `"windturbine_anomaly_detector"`       |
      | `udfs`                  | Configuration for the User-Defined Functions (UDFs).                                           | See below for details.                 |

      **UDFs Configuration**:

      The `udfs` section specifies the details of the UDFs used in the task.

      | Key     | Description                                                                 | Example Value                          |
      |---------|-----------------------------------------------------------------------------|----------------------------------------|
      | `type`  | The type of UDF. Currently, only `python` is supported.                     | `"python"`                             |
      | `name`  | The name of the UDF script.                                                 | `"windturbine_anomaly_detector"`       |
      | `models`| The name of the model file used by the UDF.                                 | `"windturbine_anomaly_detector.pkl"`   |

      ---

      **Alerts Configuration**:

      The `alerts` section defines the settings for alerting mechanisms, such as MQTT.
      For OPC-UA configuration, please refer [Publishing OPC-UA alerts](./Custom-User-Configuration.md#publishing-opc-ua-alerts)

      **MQTT Configuration**:

      The `mqtt` section specifies the MQTT broker details for sending alerts.

      | Key                 | Description                                                                 | Example Value          |
      |---------------------|-----------------------------------------------------------------------------|------------------------|
      | `mqtt_broker_host`  | The hostname or IP address of the MQTT broker.                              | `"ia-mqtt-broker"`     |
      | `mqtt_broker_port`  | The port number of the MQTT broker.                                         | `1883`                |
      | `name`              | The name of the MQTT broker configuration.                                 | `"my_mqtt_broker"`     |


   2. **`config/`**:
      - `kapacitor_devmode.conf` would be updated as per the above `config.json` at runtime for usage.

   3. **`udfs/`**:
      - Contains the python script to process the incoming data.
        Uses Random Forest Regressor and Linear Regression machine learning algos accelerated with Intel® Extension for Scikit-learn*
        to run on CPU to detect the anomalous power generation data points relative to wind speed.

   4. **`tick_scripts/`**:
      - The TICKScript `windturbine_anomaly_detector.tick` determines processing of the input data coming in.
        Mainly, has the details on execution of the UDF file, storage of processed data and publishing of alerts. 
        By default, it is configured to publish the alerts to **MQTT**.
   
   5. **`models/`**:
      - The `windturbine_anomaly_detector.pkl` is a model built using the RandomForestRegressor Algo.

## Summary

This guide demonstrated how to deploy and use the Wind Turbine Anomaly Detection pipeline to identify anomalies in wind turbines. For more details, refer to the [Overview](./Overview.md).
