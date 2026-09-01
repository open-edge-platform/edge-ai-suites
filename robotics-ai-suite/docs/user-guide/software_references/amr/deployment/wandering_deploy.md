# Deploying `wandering`

This software reference deploys the Wandering workflow on a Clearpath Jackal with an
RealSense camera. The application uses RTAB-Map and Nav2 to create a
map and autonomously explore the environment.

## Prerequisites

Complete the [Clearpath Robotics Jackal setup](../../../hardware_blueprints/amr/clearpath-jackal.md)
and verify motor control before continuing.

## Install the Deployment Package

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
sudo apt update
sudo apt install ros-jazzy-wandering-jackal-tutorial
```

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
sudo apt update
sudo apt install ros-humble-wandering-jackal-tutorial
```

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

## Run the Deployment

Log in as the `administrator` user and run:

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
/opt/ros/jazzy/share/wandering_jackal_tutorial/scripts/wandering_jackal.sh
```

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
/opt/ros/humble/share/wandering_jackal_tutorial/scripts/wandering_jackal.sh
```

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

After startup, the robot begins exploring and RTAB-Map builds a map from the
RealSense camera input. Stop the workflow with `Ctrl-c`.

## Troubleshooting

For general robot issues, see the [troubleshooting guide](../../../resources/troubleshooting).