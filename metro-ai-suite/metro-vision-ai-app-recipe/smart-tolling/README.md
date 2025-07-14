# Smart Tolling
Streamline vehicle tolling operations with AI-driven video analytics for license plate recognition and multi-lane vehicle detection.

## Overview

The Smart Tolling application uses AI-driven video analytics to detect vehicles and recognize license plates across multiple lanes. It identifies vehicles in real-time and extracts license plate information with high accuracy, providing essential data for tolling systems.

This solution processes video streams from tolling points and uses deep learning models to detect vehicles and read license plates. The application monitors traffic flow across multiple lanes simultaneously and publishes this data for visualization and integration with other systems.

By leveraging cutting-edge technologies and pre-trained deep learning models, this application enables real-time processing and analysis of video streams from tolling points. Built on a modular architecture, it provides a foundation that can be extended to implement complete tolling solutions including vehicle classification and reporting.

### Key Features

- **License Plate Recognition:** Accurately detects and reads license plates from moving vehicles using specialized AI models.
- **Multi-Lane Monitoring:** Simultaneously processes video feeds from multiple lanes to track vehicles across tolling points.
- **Vehicle Detection and Classification:** Identifies different types of vehicles (cars, trucks, buses) for potential toll differentiation.
- **Integration with MQTT, Node-RED, and Grafana:** Facilitates efficient message handling, real-time monitoring, and insightful data visualization.
- **User-Friendly:** Simplifies configuration and operation through prebuilt scripts and configuration files.

## How It Works

The architecture is designed to facilitate seamless integration and operation of various components involved in AI-driven video analytics.

![Architecture Diagram](_images/arch.png)

### Components

- **DL Streamer Pipeline Server (VA Pipeline):** Processes video frames, extracts metadata, and integrates AI inference results.
- **Mosquitto MQTT Broker:** Facilitates message communication between components like Node-RED and DL Streamer Pipeline Server using the MQTT protocol.
- **Node-RED:** A low-code platform for setting up application-specific rules and triggering MQTT-based events.
- **WebRTC Stream Viewer:** Displays real-time video streams processed by the pipeline for end-user visualization.
- **Grafana Dashboard:** A monitoring and visualization tool for analyzing pipeline metrics, logs, and other performance data.
- **Inputs (Video Files and Cameras):** Provide raw video streams or files as input data for processing in the pipeline.

The DL Streamer Pipeline Server is a core component, designed to handle video analytics at the edge. It leverages pre-trained deep learning models to perform tasks such as object detection, classification, and tracking in real-time. The DL Streamer Pipeline Server is highly configurable, allowing users to adjust parameters like detection thresholds and object types to suit specific use cases. This flexibility ensures that users can deploy AI-driven video analytics solutions quickly and efficiently, without the need for extensive coding or deep learning expertise.

It integrates various components such as MQTT, Node-RED, and Grafana to provide a robust and flexible solution for real-time video inference pipelines. The tool is built to be user-friendly, allowing customization without the need for extensive coding knowledge. Validate your ideas by developing an end-to-end solution faster.

## Learn More

- [Get Started](../docs/user-guide/get-started.md)
