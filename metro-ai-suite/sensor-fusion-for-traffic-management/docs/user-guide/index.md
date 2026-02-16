# Sensor Fusion for Traffic Management

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/sensor-fusion-for-traffic-management">
     GitHub project
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/sensor-fusion-for-traffic-management/README.md">
     Readme
  </a>
</div>
hide_directive-->

A multi-modal reference implementation to accurately monitor traffic conditions by blending
camera and sensor inputs. While cameras capture high-resolution visual data, radar/lidar
sensors precisely measure the speed and distance, even under challenging conditions, such as
fog, rain, or darkness.

This integration improves on the camera-only solutions in performance, accuracy, and
reliability, offering a more robust and comprehensive approach to traffic monitoring and
management.

This sample features multiple pipelines tailored to specific sensor fusion use cases, combining
cameras with either radar or lidar:

- One camera paired with one mmWave radar (1C+1R)
- Two cameras paired with one mmWave radar (2C+1R)
- Four cameras paired with four mmWave radars (4C+4R)
- Sixteen cameras paired with four mmWave radars (16C+4R)
- Two cameras paired with one lidar (2C+1L)
- Four cameras paired with two lidars (4C+2L)
- Twelve cameras paired with two lidars (12C+2L)
- Eight cameras paired with four lidars (8C+4L)
- Twelve cameras paired with four lidars (12C+4L)

## Key Features

Discover the key features that set our implementation apart and see how it meets the sensor
fusion requirements of your intelligent traffic management solution. For a highly performant
and cost-efficient solution, leverage the  Intel-powered
[Certified AI Systems](https://www.intel.com/content/www/us/en/developer/topic-technology/edge-5g/edge-solutions/hardware.html?f:guidetm392b07c604bd49caa5c78874bcb8e3af=%5BIntel%C2%AE%20Edge%20AI%20Box%5D).
Whether you are developing a comprehensive traffic management system or showcasing your
hardware platform's capabilities, this reference implementation serves as the perfect foundation.

- Powerful and scalable CPU, built-in GPU (iGPU), dGPU configurations that deliver heterogeneous computing capabilities for sensor fusion-based AI inferencing.
- Low power consumption package with a wide temperature range, compact fanless design, and enhanced vibration resistance.
- Processors designed for industrial and embedded conditions, ensuring high system reliability.
- Optimized software reference implementation based on open-source code to support performance evaluation, rapid prototyping, and quick time-to-market.
- Rugged and compact PC design to withstand harsh in-vehicle environmental conditions.

## Benefits

- **Enhanced AI Performance**: Achieve superior AI performance with our recommended optimization techniques, rigorously tested on industry-leading AI models and sensor fusion workloads.
- **Accelerated Time to Market**: Speed up your development process by leveraging our pre-validated SDK and Intel-powered qualified AI Systems, ensuring a quicker path from concept to deployment.
- **Cost Efficiency**: Lower your development costs with royalty-free developer tools and cost-effective hardware platforms, ideal for prototyping, development, and validation of edge AI traffic solutions.
- **Simplified Development**: Reduce complexity with our best-known methods and streamlined approach, making it easier to build an intelligent traffic management system.

<!--hide_directive
:::{toctree}
:hidden:

Get Started <get-started-guide.md>
How it Works <how-it-works.md>
Advanced user guide <advanced-user-guide.md>
APIs.md
troubleshooting.md
release-notes.md
:::
hide_directive-->
