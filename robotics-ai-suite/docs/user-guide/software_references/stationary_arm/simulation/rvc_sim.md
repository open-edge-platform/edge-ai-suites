# Stationary Robotics Toolkit Vision and Control Simulation Reference Demo

The Stationary Robotics Toolkit Simulation Reference Demo provides a safe, virtual environment to test and validate perception pipelines, grasp planning algorithms, and MoveIt 2 Servo arm control before connecting to physical hardware.

## Simulation Environment

The simulation environment uses **Gazebo** to model physical contacts, kinematics, and sensor dynamics in an industrial workstation cell:

* **Manipulator and Gripper**: Universal Robots UR5e arm with a Robotiq 2F-85 adaptive gripper simulated with joint controllers.
* **Camera Sensor**: Simulated RGB-D camera sensor plugin publishing synthetic color images and point clouds matching the Intel RealSense D415 optical frame.
* **Workstation Environment**: Worktable surface, collision boundary volumes, and target pickable objects.

```{mermaid}
flowchart LR
    gazebo[Gazebo Simulation World] -->|Synthetic RGB-D Streams| vision[Perception Engine]
    vision --> grasp[Grasp Selection]
    grasp --> sm[State Machine]
    sm --> servo[MoveIt 2 Servo]
    servo -->|Joint Trajectory Commands| gazebo
```

## Running the Simulation

### 1. Build the Workspace
Ensure your workspace is built with the simulation packages included:

```bash
source /opt/ros/jazzy/setup.bash
colcon build --base-paths src --symlink-install
source install/setup.bash
```

### 2. Launch the Gazebo Work Cell
Start the Gazebo world containing the robot model, workstation, and simulated camera:

```bash
ros2 launch stationary_robotics_dynamic_demo gazebo_sim_launch.py
```

### 3. Launch RViz2 and Task Orchestration
In separate terminals, start the visualization interface, perception pipeline, and state machine:

* **Terminal 2: RViz2 Visualization & Collision Scene**
  ```bash
  ros2 launch stationary_robotics_dynamic_demo rviz2_launch.py
  ```

* **Terminal 3: Vision Perception Pipeline**
  ```bash
  ros2 launch stationary_robotics_vision_main vision.composition.launch.py use_sim_time:=true
  ```

* **Terminal 4: State Machine Orchestrator**
  ```bash
  ros2 launch stationary_robotics_dynamic_demo dynamic_demo_launch.py \
    use_sim_time:=true \
    use_mock_hardware:=false \
    motion_controller:=servo
  ```

## Testing with Mock Hardware (Physics-Free Mode)

If you wish to test state machine transitions, node communication, and trajectory generation without running full Gazebo physics, use mock hardware mode:

```bash
ros2 launch stationary_robotics_dynamic_demo dynamic_demo_launch.py \
  use_mock_hardware:=true \
  rs_model:=d415 \
  motion_controller:=servo
```

In mock hardware mode, the UR ROS 2 driver simulates joint position state feedback internally, allowing rapid validation of waypoint sequencing and MoveIt 2 Servo velocity outputs in RViz2.

## Validating the Simulation Run

1. **Verify Perception Outputs**: Check that `stationary_robotics_rotated_object_detection` detects simulated objects in the synthetic RGB feed and publishes bounding boxes on `<namespace>/inference_detection_image`.
2. **Inspect Trajectory Execution**: Confirm in RViz2 that MoveIt 2 Servo plans smooth Cartesian approaches toward target objects without triggering collision warnings against defined collision boxes.
3. **Verify Grasp and Place Sequencing**: Observe the simulated gripper closing around the target object and transferring it to the drop waypoint before returning to the safe home pose.

## Next Steps

Once the application workflow operates reliably in simulation, proceed to deploy on physical hardware:
* Review the [UR5e Vision and Controls Deployment Configuration](../../../hardware_blueprints/stationary_arm/ur5e-robotiq-realsense.md) for cabling, URCap setup, and calibration steps.
* Execute the [Stationary Robot Toolkit Vision and Controls Deployment Demo](../deployment/rvc_deploy.md).
