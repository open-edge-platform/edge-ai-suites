# Release Notes: Robotics AI Suite 2026.1

**June 17, 2026**

## Autonomous Mobile Robot

**Version 2026.1**

**New**

- Added automated one-command ROS 2 environment setup scripts (setup-robotics-humble.sh and setup-robotics-jazzy.sh) that install the full AMR stack (ROS 2, OpenVINO, Intel RealSense SDK, Robotics SDK, Collaborative SLAM) for Ubuntu Humble and Jazzy respectively.
- Added ISX031 industrial camera support in multicam-demo with a new config/config_isx031_4cameras.js configuration file and extended CameraCapWrapper to accept Linux device paths (e.g. /dev/video-isx031-a-0) in addition to integer camera indices.
- Added Level 2 end-to-end pipeline KPI analysis to ros-kpi via a new analyze_pipeline_latency.py tool that computes per-stage latency, throughput, and drop rate across the full AMR processing pipeline.
- Added Grafana live metrics dashboard integration for ros-kpi, including a new demo_interactive_heatmap.py script for interactive visualization of KPI data and a GRAFANA_QUICKSTART.md guide for rapid dashboard setup.
- Added JSON schema files (kpi_level1_v1.json, kpi_level2_v1.json) for structured validation of KPI output data.

**Improved**

- ros-kpi: ros2_graph_monitor.py now uses ROS message header timestamps instead of wall-clock time for accurate latency measurement in both real-time and Gazebo simulated environments; added \--use-sim-time CLI flag and auto-detection of the /clock topic.
- ros-kpi: Added \--csv-out and \--xlsx-out flags to analyze_trigger_latency.py for exporting KPI results to CSV and Excel formats; added a smoke-test suite (tests/test_csv_export.py) for the export functionality.
- ros-kpi: Standalone wandering-benchmark, picknplace-benchmark, and analyze-benchmark Makefile targets, replacing the former delegating approach; added a Level 2 KPI option (option 6) to the interactive quickstart menu.
- Multicam-demo: Camera configuration files now support per-camera width, height, and format (FOURCC pixel format, e.g. YUYV, MJPG) fields passed directly to CameraCapWrapper; added \--duration flag for headless timed runs; added run summary with per-camera FPS and pre/submit timing statistics; improved async inference thread cleanup on shutdown by draining in-flight inferences.
- Multicam-demo: Added \--no-display flag for fully headless operation and \--verbose flag for per-camera frame statistics printed every two seconds.
- PicknPlace simulation (Gazebo): CMake build for ROS Jazzy corrected by adding find_package for gz-sim8, gz-msgs10, sdformat14, and Protobuf and fixing imported target names; added libprotobuf-dev build dependency; added pytest-based functional test suite covering launch file structure and UR5 robot configuration.
- Intel oneAPI runtime, compiler, and MKL packages pinned to version 2025.3.* in both collaborative-slam and multicam-demo, preventing unintended automatic upgrades that could break compatibility.
- Setup scripts hardened with set -o errexit, set -o errtrace, set -o pipefail, and a failure handler ERR trap, so installation failures are reported with the failing step name instead of silently continuing.
- Setup scripts: Changed all apt calls to apt-get for scripting best-practice compliance; added \--allow-downgrades when installing ros-*-librealsense2 to accommodate pinned version constraints; reordered RealSense installation to run the ROS wrapper package before the DKMS kernel module and SDK.

**Fixed**

- adbscan (Follow-Me): Initialized new_target_loc to zero before use in adbscan_sub.cpp, adbscan_sub_w_gesture.cpp, and adbscan_sub_w_gesture_audio.cpp, preventing potential undefined behavior when no target has been detected yet; fixed an uninitialized pointer in doDBSCAN.cpp.
- adbscan: Fixed the license-check Makefile target to reference the public fsfe/reuse:5.0.2 Docker image instead of an internal registry path, allowing license checks to run without internal network access.
- Multicam-demo: Fixed hardcoded absolute model path (/opt/ros/humble/share/pyrealsense2-ai-demo/...) to use a relative models/yolov8/FP16/... path, restoring compatibility with uv-managed Python environments.
- Multicam-demo: Fixed generate_ai_models.sh model conversion script to call mo.py directly rather than capturing its output, correcting exit-code handling.
- Security: Updated opencv-python to 4.8.0.78 in the Follow-Me (adbscan Jazzy) requirements and bumped pillow to >=12.2.0 in ros-kpi to resolve Dependabot-flagged vulnerabilities.
- ros-kpi: Fixed the Debian packaging rules for both Humble and Jazzy to include the schemas/ directory in the installed package.
- Removed obsolete deprecated files: collaborative-slam trajectory comparison script (traj-compare.py), ITS planner run script (run_its.sh), and Debian preinst scripts from multicam-demo.


## Embodied Intelligence SDK

**Version 2026.1**

Embodied Intelligence SDK v26.1 introduces new sample pipeline - OpenClaw + AgenticROS and Intel Core Ultra 3 Platform support of below pipelines:

- Pi0.5 with RTC
- LLM Robotics Demo

**New**

- OpenClaw + AgenticROS: The sample pipeline demonstrates the integration of OpenClaw and AgenticROS AI agent frameworks on Intel PTL (Panther Lake) platform, with LLM/VLM inference served by Intel OpenVINO Model Server (OVMS) for controlling JAKA Kargo robot in a Gazebo simulation environment.

**Enhanced**

- LLM Robotics Demo: Migrate from ROS2 humble to jazzy; Support LLM `Qwen3`; Add TTS server `MeloTTS`.
- Pi0.5 with RTC: Refactor the pipeline for better evaluation in MuJoCo simulator.

## Stationary Robot Vision & Control

Click each tab to learn about the new and updated features in each release of Stationary Robot.

::::{tab-set}
:::{tab-item} RVC v2.1

RVC v2.1 release includes bug and security updates as well as Intel Lab's Histodepth Pointcloud Segmentation algorithm in a Virtual Fence application.

- **Intel Lab's Histodepth Pointcloud Segmentation Virtual Fence**: Now part of the RVC package, this virtual fence application running on ROS uses depth information from an Intel RealSense camera to create dynamic and static scene segmentation maps to enable live robotic virtual fencing and safety bounding. The use of this segmentation algorithm enables a drop-in approach to virtual fencing, requiring no training or learning before deployment.

**Features**

- New dynamic path planning algorithm available (Dobby path planner available under NDA - contact [eci.maintainer@intel.com](mailto:eci.maintainer@intel.com) for details).
- New dynamic virtual fencing algorithm available.

**Known Limitations and Issues**

:::
:::{tab-item} RVC v2.0

RVC v2.0 provides a SW framework to control a robot based on vision based object detection.
It's a collection of SW components that can be deployed provided a debian packages.
But it is expected to be customized, hardened, optimized and extended by customers before it's used as a final product.

RVC focuses on demonstrating consolidation of the following functionalities:

- Camera input
- Vision based object classification and 3D pose detection.
- Trajectory calculation to detected object pose.
- Robot control

**Features**

- Defined API between vision and control.
- 3D detection and 3D pose detection components.
- 2.5D detection and pose detection components.
- Control of ROS2 supporting Robots.
- Control of ROS2 not supported robots (example implementation for UR5).
- Simple static and dynamic use case example.

**Known Limitations and Issues**

**Debian packages:**

| Package | Deb Package | Description |
|---|---|---|
| gui-settings | `ros-humble-gui-settings_2.0.0jammy_amd64.deb` | Custom message for GUI to RVC communication Package. |
| moveit2-servo-motion-controller | `ros-humble-moveit2-servo-motion-controller_1.0.0jammy_amd64.deb` | RVC Motion controller interface-based plugin implemented using moveit2 servo. |
| non-oriented-grasp | `ros-humble-non-oriented-grasp_2.0.0jammy_amd64.deb` | Non oriented grasp plugin. |
| openvino-inference-plugin | `ros-humble-openvino-inference-plugin_2.0.0jammy_amd64.deb` | RVC AI interface-based Plugin implementing yolo V5, v6 and V8 using openvino inferencing. |
| oriented-grasp | `ros-humble-oriented-grasp_2.0.0jammy_amd64.deb` | Non oriented grasp plugin. |
| robotiq-controllers | `ros-humble-robotiq-controllers_2.0.0jammy_amd64.deb` | Provides controllers for robotiq 2f gripper. |
| robotiq-driver-plugin | `ros-humble-robotiq-driver-plugin_2.0.0jammy_amd64.deb` | Robotiq 2f driver. |
| rvc-ai-interface | `ros-humble-rvc-ai-interface_2.0.0jammy_amd64.deb` | Interface every 2.5D AI plugin shall inmplement. |
| rvc-dynamic-motion-controller-use-case | `ros-humble-rvc-dynamic-motion-controller-use-case_2.0.0jammy_amd64.deb` | Main package for RVC motion controller. |
| rvc-grasp-interface | `ros-humble-rvc-grasp-interface_2.0.0jammy_amd64.deb` | Pluginlib interface that a pose to grasp plugin has to implement. |
| rvc-messages | `ros-humble-rvc-messages_2.0.0jammy_amd64.deb` | RVC vision interface messages. |
| rvc-motion-controller-interface | `ros-humble-rvc-motion-controller-interface_2.0.0jammy_amd64.deb` | Interface defining how motion controller plugins shall be implemented. |
| rvc-object-detection-engine | `ros-humble-rvc-object-detection-engine_2.0.0jammy_amd64.deb` | AI inference pipeling Stage 1 object detection engine, plugin based to allow different AI models, and devices. |
| rvc-packages-all | `ros-humble-rvc-packages-all_2.0.0jammy_amd64.deb` | Metapackage aggreating all RVC packages. |
| rvc-panel-rviz2-plugin | `ros-humble-rvc-panel-rviz2-plugin_2.0.0jammy_amd64.deb` | RVC controls for RViz. |
| rvc-pose-detector | `ros-humble-rvc-pose-detector_2.0.0jammy_amd64.deb` | AI pose alignment stage Package. |
| rvc-profiler | `ros-humble-rvc-profiler_2.0.0jammy_amd64.deb` | Node to gather various statistics of RVC. |
| rvc-rotated-object-detection | `ros-humble-rvc-rotated-object-detection_2.0.0jammy_amd64.deb` | Rotated object detection using ORB features. |
| rvc-static-motion-controller-use-case | `ros-humble-rvc-static-motion-controller-use-case_2.0.0jammy_amd64.deb` | Main package for RVC motion controller. |
| rvc-vision-main | `ros-humble-rvc-vision-main_2.0.0jammy_amd64.deb` | Start up and configuration files for the whole vision component. |
| rvc-vision-messages | `ros-humble-rvc-vision-messages_2.0.0jammy_amd64.deb` | Custom message between AI and motion controller. |
| state-machine-msgs | `ros-humble-state-machine-msgs_2.0.0jammy_amd64.deb` | Custom message for state machines communication Package. |
| trac-ik-kinematics-plugin | `ros-humble-trac-ik-kinematics-plugin_1.6.6jammy_amd64.deb` | A MoveIt! Kinematics plugin using TRAC-IK. |
| trac-ik-lib | `ros-humble-trac-ik-lib_0.1.0jammy_amd64.deb` | TRAC-IK is a faster, significantly more reliable drop-in replacement for KDL's pseudoinverse Jacobian solver. |
| ur-pendant-motion-controller | `ros-humble-ur-pendant-motion-controller_1.0.0jammy_amd64.deb` | Direct Universal Robot pendant controller. |

:::
:::{tab-item} RVC v1.0

Initial release of Robot Vision & Control Framework (RVC).
RVC allows closed loop automatic object recognition and robot manipulation of a set of moving objects.

**Features**

- Six Degree of Freedom (6DoF) real-time object detection
- Manipulator dynamic tracking, that is, robot adjusts trajectory towards target in real-time

**Known Limitations and Issues**

- The object set must be known prior, that is, the objects need to be present on file system in the pointcloud format, matching the real objects
- Camera position must be accurate by either adjusting the camera in a particular position or changing the position in a configuration file
- Only the Universal Robots™ family has been tested (more specifically, UR5e), the Robotiq 2F-85 Gripper and D415 Intel® RealSense™ Camera.
- Only one object can be placed under the camera. Multiple objects could work, however there are known issues. For this release, make sure that there is only one object under the camera or none.

:::
::::