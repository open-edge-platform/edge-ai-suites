# Smart Intersection

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/release-2025.2.0/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection">
     GitHub project
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/release-2025.2.0/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/README.md">
     Readme
  </a>
  <a class="icon_download" href="https://github.com/open-edge-platform/edge-ai-suites/blob/release-2025.2.0/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/docs/user-guide/get-started.md">
     Installation guide
  </a>
</div>
hide_directive-->

Smart Intersection Sample Application uses edge AI to improve traffic flow. It combines feeds from multiple cameras to track vehicles across angles, analyze speed and direction, and understand interactions in real space. The system can run on existing cameras and deliver real-time, coordinated insights for smarter traffic monitoring.

**Example Use Cases**

- **Pedestrian Safety**: Enhance safety for people crossing the street. The system tracks pedestrians at crosswalks. It alerts when people walk outside safe crossing areas.
- **Traffic Flow Monitoring**: Count vehicles and measure dwell time in each lane. The system detects when vehicles stay too long in lanes. This identifies stalled cars, accidents, and traffic jams.

**Key Benefits**

The key benefits are as follows:

- **Multi-camera multi-object tracking**: Enables tracking of objects across multiple camera views.
- **Scene based analytics**: Regions of interest that span multiple views can be easily defined on the map rather than independently on each camera view. This greatly simplifies business logic, enables more flexibility in defining regions, and allows various types of sensors to be used to track vehicles and people such as lidar and radar in addition to cameras.
- **Improved Urban Management**: Object tracks and analytics are available near-real-time on the MQTT broker to enable actionable insights for traffic monitoring and safety applications.
- **Reduced TCO**: Works with existing cameras, simplifies business logic development, and future-proofs the solution by enabling additional sensors and cameras as needed without changing the business logic.

This guide is designed to help developers understand the architecture, setup, and customization of the sample application.

<!--hide_directive
:::{toctree}

Overview
how-it-works
system-requirements
get-started
how-to-deploy-helm
how-to-use-gpu-for-inference
how-to-deploy-with-edge-orchestrator
application-security-enablement
release-notes
support
:::
hide_directive-->