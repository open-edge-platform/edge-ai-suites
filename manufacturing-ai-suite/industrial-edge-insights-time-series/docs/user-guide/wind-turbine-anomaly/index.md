# Wind Turbine Anomaly Detection

This sample app demonstrates a time series use case by detecting anomalous power generation patterns
in wind turbines, relative to wind speed. By identifying deviations, it helps
optimize maintenance schedules and prevent potential turbine failures, enhancing
operational efficiency.

## App Architecture

As seen in the following architecture diagram, the sample app at a high-level comprises of data simulators(can act as data destinations if configured) - these in the real world would be the physical devices, the generic Time Series AI stack based on **TICK Stack** comprising of Telegraf, InfluxDB, Time Series Analytics microservice using Kapacitor and Grafana.

![Time Series AI Stack Architecture Diagram](../_images/time-series-ai-stack-architecture.png)

### Data flow explanation

Let's discuss how this architecture translates to data flow in the wind turbine anomaly detection use case, by ingesting the data using the OPC-UA simulator and publishing the anomaly alerts to MQTT broker.

#### **Data Sources**

Using the `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/ingestor-data/wind-turbine-anomaly-detection.csv` which is a normalized version of open source data wind turbine dataset (`edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/training/T1.csv`) from <https://www.kaggle.com/datasets/berkerisen/wind-turbine-scada-dataset>.
This data is being ingested into **Telegraf** using the **OPC-UA** protocol using the **OPC-UA** data simulator.

#### **Data Ingestion**

**Telegraf** through its input plugins (**OPC-UA** OR **MQTT**) gathers the data and sends this input data to both **InfluxDB** and **Time Series Analytics Microservice**.

#### **Data Storage**

**InfluxDB** stores the incoming data coming from **Telegraf**.

#### **Data Processing**

**Time Series Analytics Microservice** uses the User Defined Function(UDF) deployment package(TICK Scripts, UDFs, Models) coming from the sample apps. The UDF deployment package for `Wind Turbine Anomaly Detection` sample app is available
at `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config`.

Directory details is as below:

##### **`config.json`**:

The `task` section defines the settings for the Kapacitor task and User-Defined Functions (UDFs).

| Key                     | Description                                                                                     | Example Value                          |
|-------------------------|-------------------------------------------------------------------------------------------------|----------------------------------------|
| `udfs`                  | Configuration for the User-Defined Functions (UDFs).                                           | See below for details.                 |

**UDFs Configuration**:

The `udfs` section specifies the details of the UDFs used in the task.

| Key     | Description                                                                                 | Example Value                          |
|---------|---------------------------------------------------------------------------------------------|----------------------------------------|
| `name`  | The name of the UDF script.                                                                 | `"windturbine_anomaly_detector"`       |
| `models`| The name of the model file used by the UDF.                                                 | `"windturbine_anomaly_detector.pkl"`   |
| `device`| Specifies the hardware `CPU` or `GPU` for executing the UDF model inference.Default is `cpu`| `cpu`                                  |

> **Note:** The maximum allowed size for `config.json` is 5 KB.
---

**Alerts Configuration**:

The `alerts` section defines the settings for alerting mechanisms, such as MQTT protocol.
For OPC-UA configuration, please refer [Publishing OPC-UA alerts](../how-to-guides/how-to-configure-alerts.md#helm---publish-opc-ua-alerts).
Please note to enable only one of the MQTT or OPC-UA alerts.

**MQTT Configuration**:

The `mqtt` section specifies the MQTT broker details for sending alerts.

| Key                 | Description                                                                 | Example Value          |
|---------------------|-----------------------------------------------------------------------------|------------------------|
| `mqtt_broker_host`  | The hostname or IP address of the MQTT broker.                              | `"ia-mqtt-broker"`     |
| `mqtt_broker_port`  | The port number of the MQTT broker.                                         | `1883`                |
| `name`              | The name of the MQTT broker configuration.                                 | `"my_mqtt_broker"`     |

##### **`udfs/`**

Contains the python script to process the incoming data.
Uses Random Forest Regressor and Linear Regression machine learning algos accelerated with Intel® Extension for Scikit-learn*
to run on CPU to detect the anomalous power generation data points relative to wind speed.

##### **`tick_scripts/`**

The TICKScript `windturbine_anomaly_detector.tick` determines processing of the input data coming in.
Mainly, has the details on execution of the UDF file, storage of processed data and publishing of alerts.
By default, it is configured to publish the alerts to **MQTT**.

##### **`models/`**

The `windturbine_anomaly_detector.pkl` is a model built using the RandomForestRegressor Algo.
More details on how it is built is accessible at `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/training/windturbine/README.md`

<!--hide_directive
:::{toctree}
:hidden:

how-to-enable-system-metrics

:::
hide_directive-->
