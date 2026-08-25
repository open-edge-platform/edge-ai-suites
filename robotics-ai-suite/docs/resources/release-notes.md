# Release Notes

## Version 2026.0

### Autonomous Mobile Robot 2026.0

**April 01, 2026**

Autonomous Mobile Robot has been updated to fully support ROS 2 Jazzy. This brings latest
generation ROS support on the latest Intel silicon, enabling workloads to take the
advantage of hardware accelerators such as the GPU and NPU.

**New**

- Add support for ROS 2 Jazzy across all components.
- **Warehouse Pick-and-Place Simulation**
  - Gazebo Harmonic simulation enablement
    - Migrate the warehouse pick-and-place simulation that features two manipulators (UR5) and an AMR from Gazebo Classic (Ignition) to Gazebo Harmonic:
    - Simulation launch/config stack was migrated from the older Classic/Ignition-oriented setup to a Harmonic-compatible Gazebo setup.
    - Runtime wiring was updated so Harmonic simulation components, robot descriptions, and bridges launch coherently in a single flow.
  - Plugin migration and compatibility refactor
    - Core custom simulation plugins (notably conveyor and vacuum tooling) were refactored for Harmonic behavior and plugin APIs.
    - SDF/Xacro model integration was updated to match Harmonic expectations, including resource/material compatibility adjustments.
  - Unified TF architecture for pick-and-place
    - A unified tf2-based frame system was introduced for robots and cubes.
    - New odometry-to-TF publishing was added for Harmonic DiffDrive outputs, ensuring downstream planners/controllers consume consistent transforms.
  - Controller logic moved from static offsets to TF-driven tracking
    - Arm controllers were redesigned to track target cubes from the TF tree instead of relying on hardcoded offsets.
    - Dynamic grasp pose resolution was added, improving robustness when robot/cube transforms vary at runtime.
    - Per-robot namespacing support was added for multi-robot controller separation.
  - MoveIt and manipulator control updates
    - Dedicated controller-manager configs were added for each arm.
    - Joint limits/controller config were reorganized for dual-arm operation.
    - MoveIt execution handling was hardened with longer joint-state wait tolerance and better debug behavior.
  - Robot description and tooling additions
    - New gripper/vacuum-related robot description assets were added (parallel gripper and vacuum examples).
    - URDF/SDF/control fragments were aligned to the Harmonic-ready control pipeline.
  - AMR behavior fixes required by migration
    - Navigation orientation conversion (yaw to quaternion) was corrected in AMR motion logic.
    - State-machine flow gained an explicit idle completion path for clean single-cycle demo termination.
  - Packaging and deployment updates for migrated stack
    - DDS configuration was added for runtime communication consistency.
    - Entry-point/package wiring fixes were applied for new nodes.
    - Debian package revisions were bumped to publish the migration changes cleanly.
- **Collaborative SLAM**
  - Add a safe build option and update documentation for memory management:
    - Prevention of system crashes on memory-constrained systems.
    - Support for oneAPI 2025.x/SYCL 8 development.
    - Added optional support for local ORB extractor package input during safe builds to improve compatibility with oneAPI/SYCL version requirements.
    - Updated third-party `g2o` source integration to use the ROS release repository and added explicit `libg2o` build configuration for Jazzy packaging.
    - Fully backward compatible.
  - Add the troubleshooting guide.
- **Orb-Extractor**
  - Resolved memory issues in `liborb`, improving stability and reliability under load.
  - Updated SYCL compatibility for Intel 2025.3 and introduced targeted code optimizations.
  - Introduce compatibility checks and adjustments for `OPENCV_FREE` mode in various test files.
- **ITS Planner**
  - Implemented automatic ROS distribution detection across the build and deployment pipeline
  - Updated all configuration files and documentation to support both ROS 2 Humble and Jazzy distributions
  - Added distro-specific environment variable handling `GAZEBO_MODEL_PATH` vs `GZ_SIM_RESOURCE_PATH`
  - Enhanced launch scripts with distro-aware package path resolution and configuration management
  - Added distribution-specific nav2 parameter files for optimized performance across ROS versions
  - Removed hardcoded distribution references from documentation and build scripts
- **ADBScan**
  - Jazzy + Gazebo Harmonic support enabled
    - Added and updated simulation, launch, model, packaging, and documentation assets to support ROS 2 Jazzy with Gazebo Harmonic.
    - Expanded follow-me simulation coverage across lidar, RealSense, gesture, and audio-assisted launch paths.
  - OpenVINO 2024 compatibility updates
    - Updated audio recognition components and related scripts/configuration to support OpenVINO 2024.
    - Applied changelog updates across multiple packages to reflect OpenVINO 2024 compatibility and related improvements.
  - Dependency and packaging fixes
    - Corrected Humble dependency definitions in simulation package metadata.
    - Updated Debian changelog/control-related package maintenance entries for both Humble and Jazzy package sets.
- **ROS2 KPI**
  - Introduced `ros2-kpi` (v0.1.0), a new monitoring and analysis framework for ROS2 systems.
  - Real-time ROS2 graph monitoring: nodes, topics, message rates, and processing delays across the full pipeline.
  - Automatic per-node input→output latency measurement for every node in the graph — no `--node` filter required.
  - CPU, memory, and I/O monitoring via `pidstat` with support for both thread-level and PID-only modes.
  - Cross-machine remote monitoring via SSH and DDS peer discovery (`--remote-ip`).
  - Interactive visualizations: heatmaps, timelines, core utilization, and scatter plots.
  - ROS bag analysis with per-topic latency tracking and CPU-cycle estimation.
  - Grafana dashboard integration with a Prometheus metrics exporter.
  - Unified entry point (`monitor_stack.py`) and an interactive `quickstart` launcher for guided onboarding.
  - Supports ROS2 Humble and Jazzy.

**Improved**

- **Robot configuration (robot_config)**
  - Refactor robot configuration for Gazebo Harmonic compatibility.
  - Update nav2 launch files (humble/jazzy/foxy), warehouse launch, and AMR launch.
  - Update TurtleBot3 waffle SDF models (standard, tray+camera, tray no-camera variants).
- **Pick-and-Place Controllers (picknplace)**
  - Replace hardcoded coordinate offsets in arm1_controller with TF tree lookups (`tf2_ros`).
  - `GRASP_Y_ARM` is now dynamically resolved at startup via the live TF tree with a fallback.
  - Cube tracking uses `lookup_transform` rather than manual subtraction.
  - Increase QoS depth from 1 to 10 in moveit2.
- **Debian Packaging**
  - Bump package versions: robot-config 2.3-2, picknplace 2.3-2, robot-config-plugins 3.6-2.
- **Orb-extractor**
  - Update build dependencies in the control files for Intel oneAPI DPC++ Compiler to version 2025.3.
  - Remove redundant `libgpu_orb.so` from the package installation files.
  - Adjust the test installation files to skip problematic test targets.
  - Refactor debian/rules to streamline the build process and remove redundant test builds.
  - Enhance the SYCL code to resolve namespace qualification issues and internal implementation errors.
  - Apply the aggressive clean build approach for the SYCL compilation.
  - Update `CMakeLists.txt` to reflect changes in library linking and compiler settings.
  - Modify test source files to accommodate changes in OpenCV compatibility and removed
    deprecated OpenCV includes.
  - Increase Device count.
  - Use direct memory allocation instead of memory pool for increased stability.
- **ITS Planner**
  - Update all README files to support both Humble and Jazzy distributions.
  - Update the launch scripts with distro-aware package paths and configurations.
  - Enhance the nav2 parameter files with distro-specific settings.
  - Remove hardcoded Humble references throughout documentation.
  - Improve the `collab_slam` script with automatic ROS environment detection.
- **ADBScan**
  - Update `CMakeLists.txt` to support both Humble and Jazzy with Gazebo Harmonic on Ubuntu 22.04 and 24.04 respectively.
  - Update Makefile to include the `turtlebot3_simulations` package for Jazzy builds.

**Fixed**

- **Debian Packaging**
  - Fix debian/rules executable permissions (from 644 to 755) across all packages
    (required by dpkg-buildpackage).
- **Orb-Extractor**
  - Fix a memory leak.
- **Pick-and-Place Controllers (picknplace)**
  - Fix node namespace - from `/ARM2Controller` to `/arm2/ARM2Controller`.
  - Fix `amr_goto_pose` in amr_controller to use proper yaw-to-quaternion conversion:
    (`sin(yaw/2)`, `cos(yaw/2)`) instead of `raw z=0.004`.

### Humanoid Toolkit 2026.0

Humanoid Toolkit v26.0 introduces π₀.₅ (Pi0.5) -
a Vision-Language-Action (VLA) model with open-world generalization. It is
developed by [Physical Intelligence](https://www.pi.website/blog/pi05) and
designed to serve as a "general-purpose AI brain" for diverse robotic hardware.
The model represents a significant progress in integrating advanced reasoning
with precise physical control capabilities.

**New**

- [OpenVINO](https://docs.openvino.ai) Integration: Enable Pi0.5
  pipeline policy with OpenVINO inference optimized on Intel integrated GPU
- Add a script for OpenVINO model conversion.
- [Aloha](https://tonyzhaozh.github.io/aloha/) Pipeline Support: Include example
  implementation for both simulator and real robot environments.
- Image Processing Optimization: Enhanced Pi0.5 model structure for
  improved image processing performance.
- Real-Time Chunking Demo: Demonstrate Pi0.5 with Real-Time
  Chunking (RTC) for accelerated inference on Intel Platforms.

**Known Issues**

- `CL_OUT_OF_RESOURCES` throws an exception when running the Pi0.5
  model inference with the i915 driver on an Intel Ultra 2 Platform.

  > *Workaround: Rebind to XE driver to resolve the issue.*

## Version 25.36

### Humanoid Toolkit 25.36

Humanoid Toolkit v25.36 enhances model optimization capabilities with OpenVINO™ toolkit and provides typical workflows and examples, including Diffusion Policy (DP), Robotic Diffusion Transformer (RDT), Improved 3D Diffusion Policy (IDP3), Visual Servoing (CNS) and LLM Robotic Demo. This release has also updated the real-time optimized best-known configuration (BKC) on improving AI and control performance, and supporting the Intel® Arc™ B-series graphics card (B570).

**New**

- Updated real-time optimization BKC, including BIOS and runtime optimization, balancing performance with AI and control consolidation.
- Added support for Intel® Arc™ B-series (Battlemage) graphics card (B570).
- Fixed deadlock issue when reading i915 perf event in Preempt-RT kernel.
- New EtherCAT Master stack features supporting user-space EtherCAT Master and multiple EtherCAT masters.
- Added Diffusion Policy pipeline with OpenVINO™ toolkit optimization.
- Added Robotics Diffusion Transformer (RDT) pipeline with OpenVINO toolkit optimization.
- Added Improved 3D Diffusion Policy (IDP3) model with OpenVINO toolkit optimization.
- Added Visual Servoing (CNS) model with OpenVINO toolkit optimization.
- Provided new tutorials for typical AI model optimization with OpenVINO toolkit.
- ACRN hypervisor's initial enablement on Arrow Lake platform.
- Added new Dockerfile to build containerized Robotics Development Toolkit (RDT) pipeline.
- Added pipelines:

  | Pipeline Name                                                               |   Description                                                                                                                                                     |
  |-----------------------------------------------------------------------------|  -----------------------------------------------------------------------------------------------------------------------------------------------------------------|
  | Diffusion Policy ****diffusion_policy****                                   | An innovative method for generating robot actions by conceptualizing visuomotor policy   learning as a conditional denoising diffusion process                    |
  | Robotics Diffusion Transformer (RDT) ****robotics_diffusion_transformer**** | A RDT pipeline provided for evaluating the VLA model on the simulation   task                                                                                     |
  | LLM Robotics Demo ****llm_robotics_demo****                                 | A code generation demo for robotics, interacting with a chatbot utilizing AI   technologies such as large language models (Phi-4) and computer vision (SAM, CLIP) |


**Improved**

The following model algorithms were added and optimized by OpenVINO™ toolkit:

| Algorithm                                                | Description                                                                                                                                                   |
|----------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Qwen2.5VL                                                | Qwen2.5VL ****model_tutorials****                                                                                                                             |
| Whisper                                                  | Whisper ****model_tutorials****                                                                                                                               |
| FunASR (Automatic speech recognition)                    | Refer to the FunASR Setup ****funasr-setup**** in LLM Robotics sample pipeline                                                                                |
| Visual Servoing - CNS ****model_cns****                  | A graph neural network-based solution for image servo utilizing explicit keypoints correspondence obtained from any detector-based feature matching methods   |
| Diffusion Policy ****model_dp****                        | A visuomotor policy learning model in the field of robotic visuomotor policy learning, which represents policies as conditional denoising diffusion processes |
| Improved 3D Diffusion Policy (iDP3) ****model_idp3****   | A diffusion policy model enhancing capabilities for 3D robotic manipulation tasks                                                                             |
| Robotic Diffusion Transformer (RDT-1B) ****model_rdt**** | A diffusion-based foundation model for robotic manipulation                                                                                                   |

**Known Issues**

- ACRN hypervisor feature and performance

  - iGPU performance degradation observed when using passthrough iGPU to VM on ACRN hypervisor.
  - Display becomes unresponsive in VMs when running concurrent AI workloads with iGPU SR-IOV enabled on ACRN hypervisor.

## Version 25.15

### Humanoid Toolkit 25.15

Humanoid Toolkit v25.15 provides necessary software framework, libraries, tools, BKC, tutorials and example codes to facilitate humanoid solution development on Intel® Core™ Ultra Series 2 processors (Arrow Lake-H), It provides Intel Linux LTS kernel v6.12.8 with Preempt-RT, and supports for Canonical Ubuntu OS 22.04, introduces initial support for ROS2 Humble software libraries and tools. It supports many models optimization with OpenVINO™ toolkit, and provides typical workflows and examples including ACT manipulation, ORB-SLAM3, etc.

**New**

- Provided Linux OS 6.12.8 BSP with Preempt-RT
- Provided Real-time optimization BKC
- Optimized IgH EtherCAT master with Linux kernel v6.12
- Added ACT manipulation pipeline with OpenVINO™ and Intel® Extension for PyTorch framework optimization
- Added ORB-SLAM3 pipeline focuses on real-time simultaneous localization and mapping
- Provided typical AI models optimization tutorials with OpenVINO™ toolkit
- Added pipelines:

  | Pipeline Name                                                               |   Description                                                                                                                                                     |
  |-----------------------------------------------------------------------------|  -----------------------------------------------------------------------------------------------------------------------------------------------------------------|
  | [Imitation Learning - ACT](../software_references/humanoid/sample_pipelines/imitation_learning_act.md)  | Imitation learning pipeline using Action Chunking with Transformers(ACT) algorithm to train and evaluate in simulator or real robot environment with Intel optimization                    |
  | [VSLAM: ORB-SLAM3](../software_references/humanoid/sample_pipelines/ORB_VSLAM.md)                       | One of popular real-time feature-based SLAM libraries able to perform Visual, Visual-Inertial and Multi-Map SLAM with monocular, stereo and RGB-D cameras, using pin-hole and fisheye lens models |


**Improved**

The following model algorithms were optimized by OpenVINO™ toolkit:

| Algorithm                                                                   | Description                                                                                                                                                           |
|-----------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| YOLOv8 ****model_tutorials****                                              | CNN-based object detection                                                                                                                                            |
| YOLOv12 ****model_tutorials****                                             | CNN-based object detection                                                                                                                                            |
| MobileNetV2 ****model_tutorials****                                         | CNN-based object detection                                                                                                                                            |
| SAM ****model_tutorials****                                                 | Transformer-based segmentation                                                                                                                                        |
| SAM2 ****model_tutorials****                                                | Extend SAM to video segmentation and object tracking with cross attention to memory                                                                                   |
| FastSAM ****model_tutorials****                                             | Lightweight substitute to SAM                                                                                                                                         |
| MobileSAM ****model_tutorials****                                           | Lightweight substitute to SAM (Same model architecture with SAM. See OpenVINO toolkit's SAM tutorials for model export and application)                               |
| U-NET ****model_tutorials****                                               | CNN-based segmentation and diffusion model                                                                                                                            |
| DETR ****model_tutorials****                                                | Transformer-based object detection                                                                                                                                    |
| DETR GroundingDino ****model_tutorials****                                  | Transformer-based object detection                                                                                                                                    |
| CLIP ****model_tutorials****                                                | Transformer-based image classification                                                                                                                                |
| Action Chunking with Transformers - ACT ****model_act****                   | An end-to-end imitation learning model designed for fine manipulation tasks in robotics                                                                               |
| Feature Extraction Model: SuperPoint ****model_superpoint****               | A self-supervised framework for interest point detection and description in images, suitable for a large number of multiple-view geometry problems in computer vision |
| Feature Tracking Model: LightGlue ****model_lightglue****                   | A model designed for efficient and accurate feature matching in computer vision tasks                                                                                 |
| Bird's Eye View Perception: Fast-BEV ****model_fastbev****                  | Obtaining a BEV perception is to gain a comprehensive understanding of the spatial layout and relationships between objects in a scene                                |
| Monocular Depth Estimation: Depth Anything V2 ****model_depthanythingv2**** | A powerful tool that leverages deep learning to infer 3D information from 2D images                                                                                   |

**Known Issues**

- There is a known deadlock risk and limitation to use ``intel_gpu_top`` to read i915 perf event in Preempt-RT kernel, it will be fixed with next release.
