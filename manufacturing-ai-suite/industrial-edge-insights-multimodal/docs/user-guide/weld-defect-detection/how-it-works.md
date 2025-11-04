
# Architecture

![MultiModal Weld Defect Detection Architecture Diagram](./_images/Multimodal-Weld-Defect-Detection-Architecture.png)


## 1. **Weld Data Simulator**:

The Weld Data Simulator simulates the ingestion of weld image and sensor data by reading through the set of time synchronized video and weld csv files. The ingested frames/images are published to MediaMTX RTSP server. Similarly, the ingested weld sensor data are published to Telegraf.

---

## 2. **Analytics Modules**

### 2.1 **DL Streamer Pipeline Server**

The `DL Streamer Pipeline Server` microservice reads the frames/images from the MediaMTX server, runs the configured DL weld
defect classification model, publishes the frame metadata results over MQTT and generates the webRTC stream with bounded boxes for visualization in **Grafana**.

---

### 2.2. **Time Series Analytics Microservice**

**Time Series Analytics Microservice** uses **Kapacitor** - a real-time data processing engine that enables users to analyze time series data. It reads the weld sensor data points point by point coming from **Telegraf**, runs the ML CatBoost model to identify the anomalies, writes the results into configured measurement/table in **InfluxDB** and publishes anomalous data over MQTT.
Also, publishes all the processed weld sensor data points over MQTT.

---

### 2.3 **Fusion Analytics**

**Fusion Analytics** subscribes to the MQTT topics coming out of `DL Streamer Pipeline Server` and `Time Series Analytics Microservice`, applies `AND`/`OR` logic to determine the anomalies during weld process, publishes the results over MQTT and writes the results as a measurement/table in **InfluxDB**


### 3. **Data Visualization**

**Grafana** provides an intuitive user interface for visualizing time series data stored in **InfluxDB** and also rendering the output of `DL Streamer Pipeline Server` coming as webRTC stream. Additionally, it visualizes the fusion analytics results stored in **InfluxDB**.

---

## Summary

This section provides an overview of the architecture for the Multimodal Weld Defect Detection sample app. For detailed instructions on getting started, refer to [Get Started](./get-started.md).
