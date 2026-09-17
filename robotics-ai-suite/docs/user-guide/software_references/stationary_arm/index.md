# Stationary Arm Reference Software

The Stationary Arm reference software series provide reference workflows for fixed robotic arms operating in structured environments. Built on ROS 2 and MoveIt 2 Servo, these demos showcase vision-guided pick-and-place workflows in both simulation and physical hardware deployment.

<!--hide_directive
::::{grid} 2

:::{grid-item-card}hide_directive--> **Vision and Controls Simulation Demo**
<!--hide_directive:link: simulation/rvc_sim
:link-type: doc
:link-alt: clickable cardshide_directive-->

Validate the vision-guided pick-and-place workflow in simulation before physical deployment.
<!--hide_directive:::hide_directive-->

<!--hide_directive:::{grid-item-card}hide_directive--> **Vision and Controls Deployment Demo**
<!--hide_directive:link: deployment/rvc_deploy
:link-type: doc
:link-alt: clickable cardshide_directive-->

Deploy object detection, pose and grasp selection, ROS 2 task orchestration, and arm control on a physical UR5e arm.
<!--hide_directive:::
::::
hide_directive-->

<!--hide_directive
:::{toctree}
:maxdepth: 1
:hidden:

Vision and Controls Simulation Reference <simulation/rvc_sim>
Vision and Controls Deployment Reference <deployment/rvc_deploy>
:::
hide_directive-->
