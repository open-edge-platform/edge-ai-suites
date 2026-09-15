# Stationary Arm

The Stationary Arm Blueprint utilizes the Stationary Robot Toolkit to 
provide reference workflows for fixed robotic
arms operating in structured environments such as assembly lines, inspection
stations, and material-handling cells. It brings together validated reference solutions and an end-to-end vision-guided pick-and-place demo built on ROS 2.

The current reference implementation is the **Stationary Robot Toolkit Vision
and Controls Demo**. It couples camera-based perception, grasp selection, task
orchestration, and arm control so developers can evaluate the complete path
from detecting an object to placing it at a target.

## Stationary Arm Platform and Integration

The Stationary Robotics Toolkit provides modular components that you can
combine and adapt for different robot arms and structured workspaces.
Available building blocks include camera and object-detection pipelines, pose
and orientation-aware grasp selection, ROS 2 task orchestration, and a
motion-controller interface. This separation lets you reuse the perception and
task layers while integrating a controller appropriate to the target robot.

```{mermaid}
flowchart LR
	camera[Camera]
	detection[Object Detection]
	grasp[Pose and Grasp Selection]
	task[ROS 2 Task Orchestration]
	interface[Motion-Controller Interface]
	controller[Robot Controller]
	arm[Robot Arm and End Effector]

	camera --> detection --> grasp --> task --> interface --> controller --> arm
```

Our demonstration pipeline is set up for deployment with a Universal
Robots UR5e arm, Robotiq 2F-85 gripper, and Intel RealSense camera running Robotics AI Suite. Together, they provide a baseline for
perception-to-motion integration in fixed, structured workspaces.
Configure the robot network connection, camera-to-world transform, controller,
gripper, and collision environment for the target workspace. 


## Validated Configurations

The Stationary Arm Blueprint supports the configurations below. The reference
platform targets Intel Core Ultra Series 3 and provides a reusable Robotics AI
Suite baseline. The UR5e deployment configuration verifies the complete
vision-guided pick-and-place workflow with the identified hardware and
software. A configuration is not a guarantee of broad compatibility, but is
intended as a reference baseline.


::::{grid} 2

:::{grid-item-card} **Stationary Arm Reference Platform**

Intel Core Ultra Series 3 with components selected for the target arm, end
effector, and workspace, running the Stationary Robotics Toolkit.
:::

:::{grid-item-card} **UR5e Vision and Controls Deployment**
:link: ur5e-robotiq-realsense
:link-type: doc
:link-alt: clickable cards

Intel Core Ultra Series 3 with a Universal Robots UR5e, Robotiq 2F-85 gripper,
Intel RealSense camera, and the Stationary Robotics Toolkit.
:::
::::


### Selecting a Configuration

Use the Stationary Arm reference platform when integrating toolkit components
with a target robot and workspace. Use the UR5e Vision and Controls deployment
when working with the verified UR5e, Robotiq, and RealSense configuration.

Complete the shared [System Requirements](../../platform_foundation/system_requirements.md)
and [Getting Started](../../platform_foundation/getting_started.md) guide
before installing the toolkit. Configure the robot network connection,
camera-to-world transform, controller, gripper, and collision environment for
the target workspace. Test new configurations with simulation or mock hardware
before enabling physical robot motion.

### Safety

The verified deployment demonstrates perception-to-motion integration for a
structured pick-and-place task. Hardware substitutions, different arm models,
additional cameras, and production safety systems require integration and
validation specific to the target workspace. Validation does not make a safety
claim for a production deployment; system integrators remain responsible for
risk assessment, guarding, emergency stops, and applicable safety requirements.

## Stationary Arm Development Path

Start with the Vision and Controls Simulation Demo to validate the
pick-and-place workflow before enabling physical robot motion. Then use the
Vision and Controls Deployment Demo to deploy object detection, pose and grasp selection,
ROS 2 task orchestration, and MoveIt 2 Servo arm control on the target robot.


::::{grid} 2

:::{grid-item-card} **Vision and Controls Simulation Demo**
:link: ../../software_references/stationary_arm/simulation/rvc_sim
:link-type: doc
:link-alt: clickable cards

Validate the vision-guided pick-and-place workflow in simulation. This demo is in development.
:::

:::{grid-item-card} **Vision and Controls Deployment Demo**
:link: ../../software_references/stationary_arm/deployment/rvc_deploy
:link-type: doc
:link-alt: clickable cards

Explore the vision-guided pick-and-place workflow and its ROS 2 components.
:::
::::


```{toctree}
:maxdepth: 1
:hidden:

ur5e-robotiq-realsense
```