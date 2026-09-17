# Autonomous Mobile Robot Tutorials and Demos

The Autonomous Mobile Robot (AMR) Software References provide tested and expandable pipelines for building, simulating, and deploying mobile robot navigation and mapping pipelines on Intel hardware.

<!--hide_directive
::::{grid} 2hide_directive-->

<!--hide_directive:::{grid-item-card}hide_directive--> **Simulation References**
<!--hide_directive:link: simulation/index
:link-type: doc
:link-alt: clickable cardshide_directive-->

Learn how to use simulation-focused tools and components provided in the toolkit, including Gazebo simulations and the Wandering autonomous exploration pipeline.
<!--hide_directive:::hide_directive-->

<!--hide_directive:::{grid-item-card}hide_directive--> **Deployment References**
<!--hide_directive:link: deployment/index
:link-type: doc
:link-alt: clickable cardshide_directive-->

Learn how to deploy robotics workloads to physical robot hardware, covering keyboard teleoperation, real-world mapping, and autonomous exploration.
<!--hide_directive:::
::::
hide_directive-->

## Available Software References

### Simulation
- **[Simulated Robotics with Gazebo](simulation/basic_sim.md)** — Introduces digital twin simulation in Gazebo before deploying to physical hardware.
- **[Simulating `wandering` in Gazebo](simulation/wandering_sim.md)** — Simulates the complete Wandering exploration pipeline in Gazebo with mapping, frontier selection, and Nav2.

### Hardware Deployment
- **[Deploy Robot Teleop Using a Keyboard](deployment/teleop_deploy.md)** — Validates motor control on a physical robot using keyboard teleoperation.
- **[Deploying `wandering`](deployment/wandering_deploy.md)** — Deploys the autonomous exploration pipeline on physical hardware using RTAB-Map and Nav2.

<!--hide_directive
:::{toctree}
:maxdepth: 1
:hidden:

Simulation References <simulation/index>
Deployment References <deployment/index>
:::
hide_directive-->
