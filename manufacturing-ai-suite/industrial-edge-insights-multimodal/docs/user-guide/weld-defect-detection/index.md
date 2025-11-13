# Weld Defect Detection

## App Architecture

![MultiModal Weld Defect Detection Architecture Diagram](../_images/Multimodal-Weld-Defect-Detection-Architecture.png)

## Data flow explanation

As seen in the architecture diagram above, the sample app at a high-level comprises of data simulators
Let's discuss how this architecture translates to data flow in the weld defect detection use case, by ingesting the data using the
RTSP stream and csv data over mqtt using simulator and publishing the anomaly results to MQTT broker for fusion analytics to process it.

### **Data Sources**

Using the `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal/weld-data-simulator/simulation-data/` which is a normalized version of open source data welding dataset from
[Intel_Robotic_Welding_Multimodal_Dataset](https://huggingface.co/datasets/amr-lopezjos/Intel_Robotic_Welding_Multimodal_Dataset).

The simulator reads `.avi` video files from the dataset and streams them as RTSP for vision data using the **mediamtx** server. This enables real-time video ingestion, simulating camera feeds for weld defect detection. The **dlstreamer-pipeline-server** connects to the RTSP stream and processes the video frames using a Geti model for automated defect analysis.

Timeseries data is being ingested into **Telegraf** using the **MQTT** protocol using the **weld-data-simulator** data simulator
Vision data is being ingested into **dlstreamer-pipeline-server** using the **RTSP** protocol using the **weld-data-simulator** data simulator

### **Data Ingestion**

Vision Data: **dlstreamer-pipeline-server** gathers the data through RTSP Stream using **mediamtx** as the **RTSP Server**.

Time-series Data: **Telegraf** through its input plugins (**MQTT**) gathers the data and sends this input data to both **InfluxDB** and **Time Series Analytics Microservice**.

### **Data Storage**

**InfluxDB** stores the incoming data coming from **Telegraf**, **Time Series Analytics Microservice** and **Fusion Analytics** .

### **Data Processing**

**DL Streamer Pipeline Server** sends the images with overlaid bounding boxes through webrtc protocol to webrtc browser client. This is done via the MediaMTX server used for signaling. Coturn server is used to facilitate NAT traversal and ensure that the webrtc stream is accessible on a non-native browser client and helps in cases where firewall is enabled.

#### **`DL Streamer Pipeline Server config.json`**

**Pipeline Configuration**:

| Key            | Description                                                                 | Example Value                          |
|----------------|-----------------------------------------------------------------------------|----------------------------------------|
| `name`         | The name of the pipeline configuration.                                     | `"weld_defect_classification"`        |
| `source`       | The source type for video ingestion.                                        | `"gstreamer"`                         |
| `queue_maxsize`| Maximum size of the queue for processing frames.                            | `50`                                  |
| `pipeline`     | GStreamer pipeline string defining the video processing flow from RTSP source through classification to output. | `"rtspsrc location=\"rtsp://mediamtx:8554/live.stream\" latency=100 name=source ! rtph264depay ! h264parse ! decodebin ! videoconvert ! gvaclassify inference-region=full-frame name=classification ! gvametaconvert add-empty-results=true name=metaconvert ! queue ! gvafpscounter ! appsink name=destination"` |
| `parameters`   | Configuration parameters for pipeline elements, specifically for the classification element properties. | See below for nested structure |

**Parameters Properties**:

| Key                          | Description                                                                 | Value                          |
|------------------------------|-----------------------------------------------------------------------------|--------------------------------|
| `classification-properties`  | Properties for the classification element in the pipeline.                  | Object containing element configuration |
| `element.name`               | Name of the GStreamer element to configure.                                 | `"classification"`            |
| `element.format`             | Format type for element properties.                                         | `"element-properties"`        |

**Destination Configuration**:

| Key                | Description                                                                 | Example Value                          |
|--------------------|-----------------------------------------------------------------------------|----------------------------------------|
| `destination`      | Configuration for output destinations of the pipeline.                      | Object containing metadata and frame settings |
| `metadata.type`    | The protocol type for sending metadata information.                         | `"mqtt"`                              |
| `metadata.topic`   | The MQTT topic where vision classification results are published.           | `"vision_weld_defect_classification"` |
| `frame.type`       | The protocol type for streaming video frames.                               | `"webrtc"`                            |
| `frame.peer-id`    | Unique identifier for the WebRTC peer connection.                           | `"samplestream"`                      |

---

**Time Series Analytics Microservice** uses the User Defined Function(UDF) deployment package(TICK Scripts, UDFs, Models) which is already built-in to the container image. The UDF deployment package is available
at `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal/config/time-series-analytics-microservice`. Directory details is as below:

#### **`config.json`**

**UDFs Configuration**:

The `udfs` section specifies the details of the UDFs used in the task.

| Key     | Description                                                                 | Example Value                          |
|---------|-----------------------------------------------------------------------------|----------------------------------------|
| `name`  | The name of the UDF script.                                                 | `"weld_anomaly_detector"`       |
| `models`| The name of the model file used by the UDF.                                 | `"weld_anomaly_detector.cb"`   |

> **Note:** The maximum allowed size for `config.json` is 5 KB.
---

**Alerts Configuration**:

The `alerts` section defines the settings for alerting mechanisms, such as MQTT protocol.
For OPC-UA configuration, please refer to
[Publishing OPC-UA alerts](./how-to-configure-alerts.md#publishing-opc-ua-alerts).

> **Note:** Make sure to enable only one of the MQTT or OPC-UA alerts.

**MQTT Configuration**:

The `mqtt` section specifies the MQTT broker details for sending alerts.

| Key                 | Description                                                                 | Example Value          |
|---------------------|-----------------------------------------------------------------------------|------------------------|
| `mqtt_broker_host`  | The hostname or IP address of the MQTT broker.                              | `"ia-mqtt-broker"`     |
| `mqtt_broker_port`  | The port number of the MQTT broker.                                         | `1883`                |
| `name`              | The name of the MQTT broker configuration.                                 | `"my_mqtt_broker"`     |

#### **`config/`**

`kapacitor_devmode.conf` would be updated as per the `config.json` at runtime for usage.

#### **`udfs/`**

Contains the python script to process the incoming data.
Uses Random Forest Regressor and Linear Regression machine learning algos accelerated with Intel® Extension for Scikit-learn*
to run on CPU to detect the anomalous welding using sensor.

#### **`tick_scripts/`**

The TICKScript `weld_anomaly_detector.tick` determines processing of the input data coming in.
Mainly, has the details on execution of the UDF file, storage of processed data and publishing of alerts.
By default, it is configured to publish the alerts to **MQTT**.

#### **`models/`**

The `weld_anomaly_detector.cb` is a model built using the Catboost machine learning library.

### 1. **Weld Data Simulator**

The Weld Data Simulator simulates the ingestion of weld image and sensor data by reading through the set of time synchronized video and weld csv files. The ingested frames/images are published to MediaMTX RTSP server. Similarly, the ingested weld sensor data are published to Telegraf.

---

### 2. **Analytics Modules**

#### 2.1 **DL Streamer Pipeline Server**

The `DL Streamer Pipeline Server` microservice reads the frames/images from the MediaMTX server, runs the configured DL weld
defect classification model, publishes the frame metadata results over MQTT and generates the webRTC stream with bounded boxes for visualization in **Grafana**.

---

#### 2.2. **Time Series Analytics Microservice**

**Time Series Analytics Microservice** uses **Kapacitor** - a real-time data processing engine that enables users to analyze time series data. It reads the weld sensor data points point by point coming from **Telegraf**, runs the ML CatBoost model to identify the anomalies, writes the results into configured measurement/table in **InfluxDB** and publishes anomalous data over MQTT.
Also, publishes all the processed weld sensor data points over MQTT.

---

#### 2.3 **Fusion Analytics**

**Fusion Analytics** subscribes to the MQTT topics coming out of `DL Streamer Pipeline Server` and `Time Series Analytics Microservice`, applies `AND`/`OR` logic to determine the anomalies during weld process, publishes the results over MQTT and writes the results as a measurement/table in **InfluxDB**

#### 3. **Data Visualization**

**Grafana** provides an intuitive user interface for visualizing time series data stored in **InfluxDB** and also rendering the output of `DL Streamer Pipeline Server` coming as webRTC stream. Additionally, it visualizes the fusion analytics results stored in **InfluxDB**.

---

### Summary

This section provides an overview of the architecture for the Multimodal Weld Defect Detection sample app.
Refer to the detailed instructions in [Get Started](../get-started.md).

<!--hide_directive
:::{toctree}
:hidden:

:::
hide_directive-->