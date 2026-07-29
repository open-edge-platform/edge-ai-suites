# Release Notes: Autonomous Mobile Robot


## Version 2026.1

**June 17, 2026**

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


## Version 2026.0

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
