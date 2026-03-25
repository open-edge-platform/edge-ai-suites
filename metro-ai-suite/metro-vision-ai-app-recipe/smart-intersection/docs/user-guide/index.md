# Smart Intersection

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection">
     GitHub project
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/README.md">
     Readme
  </a>
  <a class="icon_download" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/docs/user-guide/get-started.md">
     Installation guide
  </a>
</div>
hide_directive-->

The Smart Intersection sample application uses edge AI to improve the traffic flow.
It combines feeds from multiple cameras to track vehicles from different angles, analyze their
speed and direction, and understand interactions in real space. The system can be implemented
with existing cameras and deliver real-time, coordinated insights for smarter traffic monitoring.

**Example Use Cases**

- **Pedestrian Safety**: enhance safety for people crossing the street. The system tracks
  pedestrians at crosswalks and generates alerts when people walk outside safe crossing areas.
- **Traffic Flow Monitoring**: count vehicles and measure dwell time in each lane, detecting
  when vehicles stay in their lanes for too long. This identifies stalled cars, accidents,
  and traffic jams.

**Key Benefits**

- **Multi-camera multi-object tracking**: enables tracking of objects across multiple camera
  views.
- **Scene-based analytics**: regions of interest that span multiple views can be easily
  defined on the map rather than independently on each camera view. This greatly simplifies
  business logic, enables more flexibility in defining regions, and enables additional sensors
  such as lidar and radar to be used to track vehicles and people.
- **Improved Urban Management**: object tracking and analytics are available near-real-time on
  MQTT broker to enable actionable insights for traffic monitoring and safety applications.
- **Reduced TCO**: works with the existing cameras, and makes scaling with additional sensors
  and cameras easy. This simplifies business logic development, and future-proofs the solution.



## Learn More

- [Security Enablement](https://docs.openedgeplatform.intel.com/2026.0/OEP-articles/application-security.html)
- [Intel® SceneScape](https://docs.openedgeplatform.intel.com/dev/scenescape/index.html): Intel Scene-based AI software framework.
- [DL Streamer Pipeline Server](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dlstreamer-pipeline-server/index.html): Intel microservice based on Python for video ingestion and deep learning inferencing functions.

<!--hide_directive
:::{toctree}
:hidden:

get-started
how-it-works
how-to-use-gpu-for-inference
how-to-use-npu-for-inference
export-and-optimize-geti-model
troubleshooting
release-notes

:::
hide_directive-->