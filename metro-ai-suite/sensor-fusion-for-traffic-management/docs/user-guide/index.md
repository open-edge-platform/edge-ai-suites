# Sensor Fusion for Traffic Management

<!--hide_directive
<div class="component_card_widget">
   <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/sensor-fusion-for-traffic-management">
     GitHub
  </a>
   <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/sensor-fusion-for-traffic-management/README.md">
     Readme
  </a>
</div>
hide_directive-->

A multi-modal reference implementation to accurately monitor traffic conditions by fusing
camera and sensor inputs. While cameras capture high-resolution visual data, radar and lidar
sensors precisely measure speed and distance, even under challenging conditions such as fog,
rain, or darkness.

Two complementary implementations are available:

- **[Post-Fusion](post-fusion/index.md)**: the original camera + radar and camera + lidar pipelines that fuse
  independently processed sensor tracks after detection.
- **[Intermediate-Fusion](intermediate-fusion/index.md)**: a BEVFusion-based implementation that fuses camera and lidar
  features before the detection head for higher 3D object detection accuracy.

Choose the implementation that matches your sensor configuration and deployment requirements.

<!--hide_directive
:::{toctree}
:hidden:

Post-Fusion <post-fusion/index.md>
Intermediate Fusion <intermediate-fusion/index.md>
troubleshooting.md
Release Notes <release-notes.md>
:::
hide_directive-->
