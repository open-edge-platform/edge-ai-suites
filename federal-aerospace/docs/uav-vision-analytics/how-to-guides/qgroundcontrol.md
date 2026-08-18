# QGroundControl

## Installation

Follow the instructions in the QGroundControl documentation to install QGroundControl on your host machine where you are running the application.

- Latest daily build: [Download and Install QGroundControl (Ubuntu)](https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html#ubuntu)
- Stable v5.1: [Download and Install QGroundControl (Ubuntu)](https://docs.qgroundcontrol.com/Stable_V5.1/en/qgc-user-guide/getting_started/download_and_install.html#ubuntu)


## Enabling video stream in QGroundControl
Steps to enable QGroundControl to connect to the UAV Vision Analytics application video stream.

### RTSP Stream

In QGroundControl, `Click on Left top Q icon` → `Settings` → `Video` → `Source` → `select "RTSP Video Stream"` in the dropdown. Then in RTSP URL enter the URL for the desired pipeline (e.g., `rtsp://<HOST_IP>:8555/uav-mavlink-cpu`).

![QGroundControl RTSP stream](../_assets/QGC-rtsp.gif)

> **Note:** Make sure `make start-rtsp` is running in the DLSPS container before attempting to connect QGroundControl to the RTSP stream.

## Troubleshooting

- [QGroundControl — "Network Not Available" warnings](./troubleshooting.md#qgroundcontrol--network-not-available-warnings)

