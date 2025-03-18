# Pallet Defect Detection Reference Implementation

Connect video streams to multiple AI pipelines on a single industrial PC to detect the condition of pallets in a warehouse.

## Overview

Use this reference implementation to run inference workflows for multiple models and visualize the annotated output. An example use case for this reference implementation is to detect the condition of pallets in a warehouse by connecting multiple video streams from cameras to AI pipelines running on a single industrial PC.

### Features

This reference implementation offers the following features:

-   High-speed data exchange with low-latency compute.
-   AI-assisted defect detection in real-time as pallets are received at the warehouse.
-   On-premise data processing for data privacy and efficient use of bandwidth.
-   Interconnected warehouses deliver analytics for quick and informed tracking and decision making.

## How It Works

This reference implementation consists of three microservices: Edge Video Analytics Microservice (EVAM), Model Registry Microservice(MRaaS) and Multimodal Data Visualization Microservice (MDVM), as shown in Figure 1.

You start the pallet defect detection pipeline with a REST request using Client URL (cURL). The REST request will return a pipeline instance ID. EVAM then sends the images with overlaid bounding boxes via gRPC to MDVM. EVAM also sends the images to S3 compliant storage. To retrieve statistics of the running pipelines, MDVM sends a REST STATUS call and displays the received details. Any desired AI model from the Model Registry Microservice can be pulled into EVAM and used for inference in the reference implementation.

![Architecture and high-level representation of the flow of data through the architecture](./images/defect-detection-arch-diagram.png)

Figure 1: Architecture diagram

This reference implementation is built with these components:

-   <a href="https://docs.edgeplatform.intel.com/edge-video-analytics-microservice/2.2.0/user-guide/Overview.html">**Edge Video Analytics Microservice (EVAM)**</a> is an interoperable containerized microservice based on Python for video ingestion and deep learning inferencing functions.
-   <a href="https://docs.edgeplatform.intel.com/visualization-microservice/user-guide/Overview.html">**Multimodal Data Visualization Microservice**</a> enables the visualization of video streams and time-series data.
-   <a href="https://docs.edgeplatform.intel.com/model-registry-as-a-service/1.0.1/user-guide/Overview.html">**Model Registry Microservice**</a> provides a centralized repository that facilitates the management of AI models

## Learn More

-   Get started with the Pallet Defect Detection Reference Implementation by using the [Get Started Guide](../user-guide/Get-Started-Guide.md).

