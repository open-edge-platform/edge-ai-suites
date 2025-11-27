# Containers description

## Weld data simulator

The **Weld Data Simulator** module in the `Multimodal weld defect detection` sample app uses the sets of time synchronized .avi and .csv files, subset of test dataset coming from [Intel_Robotic_Welding_Multimodal_Dataset](https://huggingface.co/datasets/amr-lopezjos/Intel_Robotic_Welding_Multimodal_Dataset).
It ingests the .avi files as RTSP streams via the **mediamtx** server. This enables real-time video ingestion, simulating camera feeds for weld defect detection.
Similarly, it ingests the .csv files as data points into **Telegraf** using the **MQTT** protocol.

## Fusion Analytics

The **Fusion Analytics** module in the `Multimodal weld defect detection` sample app subscribes to the MQTT topics coming out of `DL Streamer Pipeline Server` and `Time Series Analytics Microservice`, applies `AND`/`OR` logic to determine the anomalies during weld process, publishes the results over MQTT and writes the results as a measurement/table in **InfluxDB**

# Supported versions

> **Note**: The tags suffixed with `-weekly` and `-rcX` are developmental builds, may not be stable.

## [1.0.0](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-suites/ai-suite-manufacturing/industrial-edge-insights-multimodal/release_notes/dec-2025.html#v1-0-0)

### Deploy using Docker Compose
---
For more details on deployment, refer to the [documentation](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-suites/ai-suite-manufacturing/industrial-edge-insights-multimodal/get-started.html).

# License Agreement
---
Copyright (C) 2024 Intel Corporation.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

# Legal Information
---
Intel, the Intel logo, and Xeon are trademarks of Intel Corporation in the U.S. and/or other countries.

*Other names and brands may be claimed as the property of others.
