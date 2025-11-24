# Packages List

The following is a list of Debian update packages for Embodied Intelligence SDK components.

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1 hide_directive-->

|Component Group|Package |Description |
|---|---|---|
|[BSP for Linux environment](./packages/linuxbsp.rst)|linux-intel-rt-experimental<br>linux-intel-experimental|Intel's Linux LTS real-time kernel (preempt-rt) version 6.12.8 and generic kernel version 6.12.8|
|[Linux Runtime Optimization](https://eci.intel.com/docs/3.3/appendix.html#eci-kernel-boot-optimizations)|customizations-grub|Linux environment for ECI and Intel-customized GRUB|
|[Linux firmware](https://eci.intel.com/docs/3.3/development/tutorials/enable-graphics.html)|linux-firmware|Linux firmware with Ultra iGPU firmware|
|[EtherCAT Master Stack](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/libraries/edge-control-libraries/fieldbus/ethercat-masterstack)|ighethercat<br>ighethercat-dpdk<br>ighethercat-dkms<br>ighethercat-examples<br>ighethercat-dpdk-examples<br>ecat-enablekit<br>ecat-enablekit-dpdk|Optimized open source IgH EtherCAT Master Stack for kernel space or user space|
|[Motion Control Gateway](https://eci.intel.com/docs/3.3/development/tutorials/enable-ros2-motion-ctrl-gw.html)|<br> rt-data-agent<br> ros-jazzy-agvm<br> ros-jazzy-agvm-description<br> ros-jazzy-agvm-joystick<br> ros-jazzy-agvm-nav2-helper<br> ros-jazzy-agvm-plcshm<br> ros-jazzy-agvm-plcshm-acrn<br> ros-jazzy-grasp-msgs<br> ros-jazzy-grasp-ros2<br> ros-jazzy-hiwin-ra605-710-gb-support<br> ros-jazzy-hiwin-robot-moveit-config<br> ros-jazzy-hiwin-xeg-16-support<br> ros-jazzy-run-hiwin-moveit<br> ros-jazzy-run-hiwin-plc<br> ros-jazzy-rrbot-bringup<br> ros-jazzy-rrbot-description<br> ros-jazzy-rrbot-hardware<br> ros-jazzy-rrbot-moveit-config<br> ros-jazzy-rrbot-moveit-demo<br> ros-jazzy-jaka-bringup<br> ros-jazzy-jaka-description<br> ros-jazzy-jaka-hardware<br> ros-jazzy-jaka-moveit-config<br> ros-jazzy-jaka-moveit-py<br> ros-jazzy-run-jaka-moveit<br> ros-jazzy-run-jaka-plc|The Industrial Motion-Control ROS2 Gateway is the communication bridge between DDS/RSTP wire-protocol ROS2 implementation and Motion Control (MC) IEC-61131-3 standard Intel implementation|
|[VSLAM: ORB-SLAM3](./sample_pipelines/ORB_VSLAM.rst)|<br> libpangolin<br> liborb-slam3<br> liborb-slam3-dev<br> orb-slam3|Visual SLAM demo pipeline based on ORB-SLAM3. Refer to [VSLAM: ORB-SLAM3](./sample_pipelines/ORB_VSLAM.rst) for installation and launching tutorials.|
|[Intel® RealSense™ Camera](https://wiki.ros.org/RealSense)|<br> librealsense2<br> librealsense2-dev<br> librealsense2-utils<br> librealsense2-udev-rules<br> ros-jazzy-librealsense2<br> ros-jazzy-librealsense2-tools<br> ros-jazzy-librealsense2-udev<br> ros-jazzy-realsense2-camera<br> ros-jazzy-realsense2-camera-msgs<br> ros-jazzy-realsense2-description|Intel RealSense Camera driver and tools.|
|[Imitation Learning - ACT](./sample_pipelines/imitation_learning_act.rst)|act-ov|Action Chunking with Transformers (ACT), a method that trains a generative model to understand and predict action sequences.|
|[Diffusion Policy](./sample_pipelines/diffusion_policy.rst)|diffusion-policy-ov|Diffusion Policy (DP), a method for generating robot actions by conceptualizing visuomotor policy learning as a conditional denoising diffusion process.|
|[LLM Robotics Demo](./sample_pipelines/llm_robotics.md)|funasr<br> llm-robotics|LLM Robotics demo, a code generation pipeline for robotics, which uses a large language model and vision model to generate pick and place actions.|
|[Robotics Diffusion Transformer](./sample_pipelines/robotics_diffusion_transformer.rst)|rdt-ov|Robotics Diffusion Transformer (RDT), the largest bimanual manipulation foundation model with strong generalizability.|

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: tab2 hide_directive-->

|Component Group|Package |Description |
|---|---|---|
|[BSP for Linux environment](./packages/linuxbsp.rst)|linux-intel-rt-experimental<br>linux-intel-experimental|Intel's Linux LTS real-time kernel (preempt-rt) version 6.12.8 and generic kernel version is 6.12.8|
|[Linux Runtime Optimization](https://eci.intel.com/docs/3.3/appendix.html#eci-kernel-boot-optimizations)|customizations-grub|Linux environment for ECI and Intel-customized GRUB|
|[Linux firmware](https://eci.intel.com/docs/3.3/development/tutorials/enable-graphics.html)|linux-firmware|Linux firmware with Ultra iGPU firmware|
|[EtherCAT Master Stack](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/libraries/edge-control-libraries/fieldbus/ethercat-masterstack)|ighethercat<br>ighethercat-dpdk<br>ighethercat-dkms<br>ighethercat-examples<br>ighethercat-dpdk-examples<br>ecat-enablekit<br>ecat-enablekit-dpdk|Optimized open source IgH EtherCAT Master Stack for kernel space or user space|
|[Motion Control Gateway](https://eci.intel.com/docs/3.3/development/tutorials/enable-ros2-motion-ctrl-gw.html)|<br> rt-data-agent<br> ros-humble-agvm<br> ros-humble-agvm-description<br> ros-humble-agvm-joystick<br> ros-humble-agvm-nav2-helper<br> ros-humble-agvm-plcshm<br> ros-humble-agvm-plcshm-acrn<br> ros-humble-grasp-msgs<br> ros-humble-grasp-ros2<br> ros-humble-hiwin-ra605-710-gb-support<br> ros-humble-hiwin-robot-moveit-config<br> ros-humble-hiwin-xeg-16-support<br> ros-humble-run-hiwin-moveit<br> ros-humble-run-hiwin-plc<br> ros-humble-rrbot-bringup<br> ros-humble-rrbot-description<br> ros-humble-rrbot-hardware<br> ros-humble-rrbot-moveit-config<br> ros-humble-rrbot-moveit-demo<br> ros-humble-jaka-bringup<br> ros-humble-jaka-description<br> ros-humble-jaka-hardware<br> ros-humble-jaka-moveit-config<br> ros-humble-jaka-moveit-py<br> ros-humble-run-jaka-moveit<br> ros-humble-run-jaka-plc|The Industrial Motion-Control ROS2 Gateway is the communication bridge between DDS/RSTP wire-protocol ROS2 implementation and Motion Control (MC) IEC-61131-3 standard Intel implementation|
|[VSLAM: ORB-SLAM3](./sample_pipelines/ORB_VSLAM.rst)|<br> libpangolin<br> liborb-slam3<br> liborb-slam3-dev<br> orb-slam3|Visual SLAM demo pipeline based on ORB-SLAM3. Refer to [VSLAM: ORB-SLAM3](./sample_pipelines/ORB_VSLAM.rst) for installation and launching tutorials.|
|[Intel® RealSense™ Camera](https://wiki.ros.org/RealSense)|<br> librealsense2<br> librealsense2-dev<br> librealsense2-utils<br> librealsense2-udev-rules<br> ros-humble-librealsense2<br> ros-humble-librealsense2-tools<br> ros-humble-librealsense2-udev<br> ros-humble-realsense2-camera<br> ros-humble-realsense2-camera-msgs<br> ros-humble-realsense2-description|Intel RealSense Camera driver and tools.|
|[Imitation Learning - ACT](./sample_pipelines/imitation_learning_act.rst)|act-ov|Action Chunking with Transformers (ACT), a method that trains a generative model to understand and predict action sequences.|
|[Diffusion Policy](./sample_pipelines/diffusion_policy.rst)|diffusion-policy-ov|Diffusion Policy (DP), a method for generating robot actions by conceptualizing visuomotor policy learning as a conditional denoising diffusion process.|
|[LLM Robotics Demo](./sample_pipelines/llm_robotics.md)|funasr<br> llm-robotics|LLM Robotics demo, a code generation pipeline for robotics, which uses a large language model and vision model to generate pick and place actions.|
|[Robotics Diffusion Transformer](./sample_pipelines/robotics_diffusion_transformer.rst)|rdt-ov|Robotics Diffusion Transformer (RDT), the largest bimanual manipulation foundation model with strong generalizability.|

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

<!--hide_directive
:::{toctree}
:maxdepth: 1
:hidden:

packages/linuxbsp
packages/mc_gateway
fragment_packages-jammy
:::
hide_directive-->
