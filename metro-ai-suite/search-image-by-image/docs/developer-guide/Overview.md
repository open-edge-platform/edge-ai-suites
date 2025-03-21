# Search Image by Image Sample Application
<!--REQUIRED: Add a short description without including the name of the RI/Application/microservice in the description. Ensure it's at least 50 characters (excluding spaces) and doesn't exceed 150 characters (excluding spaces). This will enable the content to be properly displayed in the catalog's card layout.-->
Performs near real-time analysis and image-based search to detect and retrieve objects of interest in large video datasets.

## Overview
The **Search Image by Image** sample application lets users search live or recorded camera feeds by providing an image and view matching objects with location, timestamp, and confidence score details.

![Screenshot of the Search Image by Image sample application interface displaying search input and matched results](./images/sibi.gif)
*Example of search results in the Search Image by Image sample application.*

This sample provides a working example of how to combine edge AI microservices for video ingestion, object detection, feature extraction, and vector-based search.

You can use this foundation to build solutions for diverse use cases, including city infrastructure monitoring and security applications, helping operators quickly locate objects of interest across large video datasets.

## How it Works
The application workflow has three stages: inputs, processing, and outputs.

![Diagram illustrating the components and interactions within the Search Image by Image system, including inputs, processing, and outputs.](images/architecture_simplified.png)
*Search Image by Image system overview diagram.*

### Inputs

- Video files or live camera streams (simulated or real time)
- User-provided images or images captured from video for search

The application includes a demonstration video for testing. The video loops continuously and appears in the UI as soon as the application starts.

### Processing

- **Video analysis with Edge Video Analytics Microservice (EVAM) and MediaMTX**: Select **Analyze Stream** to start the EVAM pipeline. EVAM processes video through **MediaMTX**, which simulates remote video cameras and publishes live streams. EVAM extracts frames and detects objects in each frame, publishing predictions through **MQTT**.
- **Feature extraction with Feature Matching**: EVAM sends metadata and images through MQTT to the Feature Matching microservice. Feature Matching generates feature vectors. If predictions exceed the threshold, the system stores vector embeddings in MilvusDB and saves frames in the Docker file system.
- **Storage and retrieval in MilvusDB**: MilvusDB stores feature vectors. You can review them in MilvusUI.
- **Video search with ImageIngestor**: To search, first analyze the stream by selecting **Analyze Stream**. Then upload an image or capture an object from the video using **Upload Image** or **Capture Frame**. You can adjust the frame to capture a specific object. The system ingests images via ImageIngestor, processes them with EVAM, and matches them against stored feature vectors in MilvusDB.

### Outputs

- Matched search results, including metadata, timestamps, confidence scores, and frames

## Minimum system requirements

- **Processor:** Intel® Ultra 7-155H
- **Memory:** 8 GB
- **Disk space:** 256 GB SSD
- **GPU/Accelerator:** Intel Arc Graphics
- **Operating system:** Ubuntu 20.04 LTS or Windows 10/11 with WSL 2

## Learn More
- [Get Started](get-started.md)
- [Architecture Overview](overview-architecture.md)
