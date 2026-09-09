# Stationary Arm Reference Software

The Stationary Arm reference software series provide reference workflows for fixed robotic arms operating in structured environments. Built on ROS 2 and MoveIt 2 Servo, these demos showcase vision-guided pick-and-place workflows in both simulation and physical hardware deployment.


::::{grid} 2

:::{grid-item-card} **Vision and Controls Simulation Demo**
:link: simulation/rvc_sim
:link-type: doc
:link-alt: clickable cards

Validate the vision-guided pick-and-place workflow in simulation before physical deployment.
:::

:::{grid-item-card} **Vision and Controls Deployment Demo**
:link: deployment/rvc_deploy
:link-type: doc
:link-alt: clickable cards

Deploy object detection, pose and grasp selection, ROS 2 task orchestration, and arm control on a physical UR5e arm.
:::
::::



:::{toctree}
:maxdepth: 1
:hidden:

Vision and Controls Simulation Reference <simulation/rvc_sim>
Vision and Controls Deployment Reference <deployment/rvc_deploy>
:::

