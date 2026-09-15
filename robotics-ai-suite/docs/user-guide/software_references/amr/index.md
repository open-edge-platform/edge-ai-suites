# Autonomous Mobile Robot Tutorials and Demos

The Autonomous Mobile Robot (AMR) Software References provide tested and expandable pipelines for building, simulating, and deploying mobile robot navigation and mapping pipelines on Intel hardware.


::::{grid} 2

:::{grid-item-card} **Simulation References**
:link: simulation/index
:link-type: doc
:link-alt: clickable cards

Learn how to use simulation-focused tools and components provided in the toolkit, including Gazebo simulations and the Wandering autonomous exploration pipeline.
:::

:::{grid-item-card} **Deployment References**
:link: deployment/index
:link-type: doc
:link-alt: clickable cards

Learn how to deploy robotics workloads to physical robot hardware, covering keyboard teleoperation, real-world mapping, and autonomous exploration.
:::
::::


## Available Software References

### Simulation
- **[Simulated Robotics with Gazebo](simulation/basic_sim.md)** — Introduces digital twin simulation in Gazebo before deploying to physical hardware.
- **[Simulating `wandering` in Gazebo](simulation/wandering_sim.md)** — Simulates the complete Wandering exploration pipeline in Gazebo with mapping, frontier selection, and Nav2.

### Hardware Deployment
- **[Deploy Robot Teleop Using a Keyboard](deployment/teleop_deploy.md)** — Validates motor control on a physical robot using keyboard teleoperation.
- **[Deploying `wandering`](deployment/wandering_deploy.md)** — Deploys the autonomous exploration pipeline on physical hardware using RTAB-Map and Nav2.


:::{toctree}
:maxdepth: 1
:hidden:

Simulation References <simulation/index>
Deployment References <deployment/index>
:::

