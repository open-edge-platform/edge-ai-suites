# Image-Based Video Search Sample Application
<!--REQUIRED: Add a short description without including the name of the RI/Application/microservice in the description. Ensure it's at least 50 characters (excluding spaces) and doesn't exceed 150 characters (excluding spaces). This will enable the content to be properly displayed in the catalog's card layout.-->
Performs near real-time analysis and image-based search to detect and retrieve objects of interest in large video datasets.

## Overview
The **Image-Based Video Search** sample application lets users search live or recorded camera feeds by providing an image and view matching objects with location, timestamp, and confidence score details.

This sample provides a working example of how to combine edge AI microservices for video ingestion, object detection, feature extraction, and vector-based search.

You can use this foundation to build solutions for diverse use cases, including city infrastructure monitoring and security applications, helping operators quickly locate objects of interest across large video datasets.

## How it Works
The application workflow has three stages: inputs, processing, and outputs.

![Diagram illustrating the components and interactions within the Image-Based Video Search system, including inputs, processing, and outputs.](docs/user-guide/_images/architecture_simplified.png)

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

![Screenshot of the Image-Based Video Search sample application interface displaying search input and matched results](docs/user-guide/_images/imagesearch2.png)

### Learn More
- [System Requirements](docs/user-guide/system-requirements.md)
- [Get Started](docs/user-guide/get-started.md)
- [Architecture Overview](docs/user-guide/overview-architecture.md)
- [How to Deploy with Helm](docs/user-guide/how-to-deploy-helm.md)
- [How to Deploy with the Edge Orchestrator](docs/user-guide/how-to-deploy-edge-orchestrator.md)
- [Release Notes](docs/user-guide/release-notes.md)

## Important Notice

This reference implementation is designed to facilitate smart cities application development. It is not intended for police, military or similar surveillance uses, use as part of critical infrastructure operations, determining access to education or other significant resource, managing workers or evaluating employment performance.

This reference implementation is intended to allow users to examine and evaluate Image-Based Video Search application and the associated performance of Intel technology solutions. The accuracy of computer models is a function of the relation between the data used to train them and the data that the models encounter after deployment. This model has been tested using datasets that may not be sufficient for use in production applications. Accordingly, while the model may serve as a strong foundation, Intel recommends and requests that this model be tested against data the model is likely to encounter in specific deployments.

Intel is committed to respecting human rights and avoiding causing or contributing to adverse impacts on human rights. See Intel’s Global Human Rights Principles. Intel’s products and software are intended only to be used in applications that do not cause or contribute to adverse impacts on human rights.

## Licensing Information

**FFmpeg**: FFmpeg is an open source project licensed under LGPL and GPL. See [FFmpeg Legal Information](https://www.ffmpeg.org/legal.html). You are solely responsible for determining if your use of FFmpeg requires any additional licenses. Intel is not responsible for obtaining any such licenses, nor liable for any licensing fees due, in connection with your use of FFmpeg.

**GStreamer**: GStreamer is an open source framework licensed under LGPL. See [GStreamer Licensing Information](https://gstreamer.freedesktop.org/documentation/frequently-asked-questions/licensing.html). You are solely responsible for determining if your use of GStreamer requires any additional licenses. Intel is not responsible for obtaining any such licenses, nor liable for any licensing fees due, in connection with your use of GStreamer.
