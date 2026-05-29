# Release Notes: Smart Traffic Intersection Agent

## Version 2026.1.0-rc1

**May 14, 2026**

- Integrate Live Metric Service and Collector for telemetry with multi-instance support (Docker and Helm)
- Update Smart Intersection RI to release-2026.0.0 version
- Migrate VLM serving from custom container to [OpenVINO Model Server (OVMS)](https://docs.openvino.ai/nightly/model-server/ovms_what_is_openvino_model_server.html) for improved inference performance and maintainability
- Add `response_format` (JSON schema) support for structured VLM output via OVMS structured generation
- Support configurable VLM model selection — `OpenVINO/InternVL2-1B-int4-ov` and `OpenVINO/Phi-3.5-vision-instruct-int8-ov` validated
- Automatic model export and conversion in Helm init container using OVMS export tooling
- Add alert deduplication and short-analysis fallback for improved VLM response handling

**Known Issues**
- VLM Openvino Serving container supported additional telemetry data that OpenVINO Model Server (OVMS) does not expose which may result in loss of telemetry information.

## Version 1.0.0

**April 01, 2026**

Smart Traffic Intersection Agent (STIA) is a new addition to the Metro AI Sute. It showcases
Hybrid AI usage in combination with the Smart Route Planning Agent (SRPA) sample application,
acting as an agent deployed at the edge (traffic intersection in this case) and providing rich
data on the “what” and “why” of the surrounding events, using SceneScape and VLMs respectively.
It provides a *UI to visualize the events* at the intersection, reporting on the number of
vehicles, showing the feed from the camera, and explaining the traffic situation.

The sample is intended to mimic a real-world deployment scenario of an orchestrating agent in
the cloud that communicates with numerous agents deployed at the edge to realize a particular
goal. For example, it tracks the number of vehicles at the intersection and if the traffic is
heavy, it reports the reason. The default prompt is tuned to look for weather and accidents
as sources of a traffic buildup.

**New**

- **Real-time Traffic Analysis**: Comprehensive directional traffic density monitoring with MQTT integration.
- **VLM Integration**: Vision Language Model (VLM)-powered traffic scene analysis with sustained traffic detection.
- **Sliding Window Analysis**: 15-second sliding window with 3-second sustained threshold for accurate traffic state detection.
- **Camera Image Management**: Intelligent camera image retention and coordination between API and VLM services.
- **RESTful API**: Complete HTTP API for traffic summaries, intersection monitoring, and VLM analysis retrieval.
- **Helmchart Support**: Support for helmchart for the application is included.
- **Concurrency Control**: Semaphore-based VLM worker management for optimal resource utilization.
- **Image Retention Logic**: Camera images persist with VLM analysis for consistent data correlation.
- **Enhanced Error Handling**: Comprehensive error management across MQTT, VLM, and image services.

**Known Issues**

- This release includes only limited testing on EMT‑S and EMT‑D, some behaviors may not yet
  be fully validated across all scenarios.
