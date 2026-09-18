# Smart Building Digital Twin

Smart Building Digital Twin is a complete smart-building monitoring simulation that
includes the end-to-end deployment: inputs, processing, analytics, dashboard,
configuration, and startup scripts.

The sample application uses synchronized cameras, YOLOX-S and ATSS-MobileNetV2 model
variants, and sensors to watch a building for:

- People, luggage, and doors
- Replayed sensor events of badge, FaceID, and ambient-light changes
- Possible falls and luggage-related events
- Abandoned, stolen, or exchanged luggage
- Door states and region occupancy
- System telemetry, including CPU, GPU, memory, storage, and CPU SKU

The system runs with Docker Engine and Docker Compose tool, and Scenescape. Camera
videos and sensor data are replayed in synchronization. Camera detections, tracking
data, and sensor events are exchanged through the Message Queuing Telemetry Transport
(MQTT) protocol and analyzed by Python programs.

An AI analytics web dashboard shows simulated building activity, alerts, camera
snapshots, and system health. The setup.sh script downloads required images and
plugins, configures the deployment, and starts the services, while configuration
files control the cameras, YOLOX-S and ATSS-MobileNetV2 model variants, scenes, and
tracking behavior.

## Next Steps

- [Get Started](./get-started.md)

<!--hide_directive
:::{toctree}
:hidden:

get-started
how-it-works
how-to-use-application
api-reference
troubleshooting
Release Notes <release-notes>

:::
hide_directive-->
