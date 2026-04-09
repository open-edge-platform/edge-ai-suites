# Live Video Captioning

This application deploys AI-powered captioning for live RTSP video streams with Deep Learning Streamer (DL Streamer) and OpenVINO™ Vision Language Models (VLMs).

![Overview](./docs/user-guide/_assets/demo.gif)

## Get Started

To see the system requirements and other installations, see the following guides:

- [System Requirements](./docs/user-guide/get-started/system-requirements.md): Check the hardware and software requirements for deploying the application.
- [Get Started](./docs/user-guide/get-started.md): Follow step-by-step instructions to set up the application.

## How It Works

The overall infrastructure involves ingesting an RTSP stream, processing it through a DLStreamer pipeline that samples frames for VLM inference, and delivering the resulting insights to the dashboard.

![System Architecture Diagram](./docs/user-guide/_assets/architecture.jpg)

For more information see [How it works](./docs/user-guide/how-it-works.md)


## Learn More

- [Overview](./docs/user-guide/index.md)
- [System Requirements](./docs/user-guide/get-started/system-requirements.md)
- [Get Started](./docs/user-guide/get-started.md)
- [Deploy with Helm](./docs/user-guide/deploy-with-helm.md)
- [API Reference](./docs/user-guide/api-reference.md)
- [How to Build Source](./docs/user-guide/get-started/build-from-source.md)
- [Known Issues](./docs/user-guide/known-issues.md)
- [Release Notes](./docs/user-guide/release-notes.md)
