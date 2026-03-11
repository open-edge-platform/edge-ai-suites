# Release Notes: Autonomous Mobile Robot

## Version 2026.0

**April 01, 2026**

Autonomous Mobile Robot has been updated to fully support ROS 2 Jazzy. This brings latest
generation ROS support on the latest Intel silicon, enabling workloads to take the
advantage of hardware accelerators such as the GPU and NPU.

**New**

- Add support for ROS 2 Jazzy across all components.
- **Simulations**
  - Migrate the pick-and-place simulation from Gazebo Classic (Ignition) to Gazebo Harmonic:
    - Replace `sim_ignition` with `sim_gazebo` across all launch files and plugin configurations.
    - Update vacuum tool plugin and conveyor belt plugin for Gazebo Harmonic joint management API.
  - Add `cyclonedds.xml` for DDS middleware configuration.
  - Add the `odom_tf_publisher` node to bridge Gazebo Harmonic's DiffDrive odometry to the
    ROS TF tree (required because the Harmonic DiffDrive plugin no longer publishes TF directly).
- **Robot configuration (robot_config)**
  - Add MoveIt controller manager configurations for arm1 and arm2.
  - Add `joint_limits_arm1.yaml` / `joint_limits_arm2.yaml` per-arm joint limit configs.
  - Add parallel gripper URDF xacro and vacuum VG4 example xacro.
  - Add the `robot_config.dsv.in` environment hooks for Humble and Jazzy.
- **Collaborative SLAM**
  - Add a safe build option and update documentation for memory management:
    - Prevention of system crashes on memory-constrained systems.
    - Support for oneAPI 2025.x/SYCL 8 development.
    - A generic and environment-agnostic approach.
    - Fully backward compatible.
  - Add the troubleshooting guide.
- **Pick-and-Place Controllers (picknplace)**
  - Add Idle SMACH state in amr_controller for a clean single-cycle demo completion.
  - Add 30s timeout waiting for joint states with a descriptive error log, and
    DEBUG-level logging for `move_to_pose calls` in moveit2.
  - Register `amr_controller` as an entry point in `setup.py`.
- **Orb-Extractor**
  - Add a debugging framework.
  - Introduce compatibility checks and adjustments for `OPENCV_FREE` mode in various test files.
- **ITS Planner**
  - Add automatic ROS distro detection to `install_deb_relocalization_pkgs.sh`.
  - Add a distro-specific environment variable handling (`GAZEBO_MODEL_PATH` vs `GZ_SIM_RESOURCE_PATH`).
- **ADBScan**
  - Add `ros-jazzy-gazebo-ros-pkgs` to `debian/control` Build-Depends and runtime Depends.
  - Add notes on support for Jazzy to the debian changelog.

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
  - Update `CMakeLists.txt` to support both Humble and Jazzy with Gazebo Harmonic on Ubuntu 24.04.
  - Update Makefile to include the `turtlebot3_simulations` package for Jazzy builds.
  - Update the version in the `package.xml` to match debian changelog (2.3.0).

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
