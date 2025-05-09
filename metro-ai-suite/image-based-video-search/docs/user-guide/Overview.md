# Image-Based Video Search Sample Application
<!--REQUIRED: Add a short description without including the name of the RI/Application/microservice in the description. Ensure it's at least 50 characters (excluding spaces) and doesn't exceed 150 characters (excluding spaces). This will enable the content to be properly displayed in the catalog's card layout.-->
Performs near real-time analysis and image-based search to detect and retrieve objects of interest in large video datasets.

## Overview
The **Image-Based Video Search** sample application lets users search live or recorded camera feeds by providing an image and view matching objects with location, timestamp, and confidence score details.

This sample provides a working example of how to combine edge AI microservices for video ingestion, object detection, feature extraction, and vector-based search.

You can use this foundation to build solutions for diverse use cases, including city infrastructure monitoring and security applications, helping operators quickly locate objects of interest across large video datasets.

## How it Works
The application workflow has three stages: inputs, processing, and outputs.

![Diagram illustrating the components and interactions within the Image-Based Video Search system, including inputs, processing, and outputs.](_images/architecture_simplified.png)

### Inputs

- Video files or live camera streams (simulated or real time)
- User-provided images or images captured from video for search

The application includes a demonstration video for testing. The video loops continuously and appears in the UI as soon as the application starts.

### Processing

- **Video analysis with Deep Learning Streamer Pipeline Server and MediaMTX**: Select **Analyze Stream** to start the DL Streamer Pipeline Server pipeline. The Pipeline Server processes video through **MediaMTX**, which simulates remote video cameras and publishes live streams. The Pipeline Server extracts frames and detects objects in each frame, publishing predictions through **MQTT**.
- **Feature extraction with Feature Matching**: DL Streamer Pipeline Server sends metadata and images through MQTT to the Feature Matching microservice. Feature Matching generates feature vectors. If predictions exceed the threshold, the system stores vector embeddings in MilvusDB and saves frames in the Docker file system.
- **Storage and retrieval in MilvusDB**: MilvusDB stores feature vectors. You can review them in MilvusUI.
- **Video search with ImageIngestor**: To search, first analyze the stream by selecting **Analyze Stream**. Then upload an image or capture an object from the video using **Upload Image** or **Capture Frame**. You can adjust the frame to capture a specific object. The system ingests images via ImageIngestor, processes them with DL Streamer Pipeline Server, and matches them against stored feature vectors in MilvusDB.

### Outputs

- Matched search results, including metadata, timestamps, confidence scores, and frames

![Screenshot of the Image-Based Video Search sample application interface displaying search input and matched results](_images/imagesearch2.png)

### Deployment with Edge Orchestrator

- [This sample application is ready for deployment with Edge Orchestrator. Download the deployment package and follow the instructions](https://docs.openedgeplatform.intel.com/edge-ai-suites/image-based-video-search/main/user-guide/how-to-deploy-edge-orchestrator.html).


### Learn More
- [System Requirements](https://docs.openedgeplatform.intel.com/edge-ai-suites/image-based-video-search/main/user-guide/system-requirements.html)
- [Get Started](https://docs.openedgeplatform.intel.com/edge-ai-suites/image-based-video-search/main/user-guide/get-started.html)
- [Architecture Overview](https://docs.openedgeplatform.intel.com/edge-ai-suites/image-based-video-search/main/user-guide/overview-architecture.html)
- [How to Build from Source](https://docs.openedgeplatform.intel.com/edge-ai-suites/image-based-video-search/main/user-guide/how-to-build-source.html)
- [How to Deploy with Helm](https://docs.openedgeplatform.intel.com/edge-ai-suites/image-based-video-search/main/user-guide/how-to-deploy-helm.html)
- [How to Deploy with the Edge Orchestrator](https://docs.openedgeplatform.intel.com/edge-ai-suites/image-based-video-search/main/user-guide/how-to-deploy-edge-orchestrator.html)
- [Release Notes](https://docs.openedgeplatform.intel.com/edge-ai-suites/image-based-video-search/main/user-guide/release-notes.html)
