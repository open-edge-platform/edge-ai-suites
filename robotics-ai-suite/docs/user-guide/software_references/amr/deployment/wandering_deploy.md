# Deploying `wandering`

This software reference deploys the Wandering workflow on a Clearpath Jackal with an
RealSense camera. The application uses RTAB-Map and Nav2 to create a
map and autonomously explore the environment.

## Prerequisites

Complete the [Clearpath Robotics Jackal setup](../../../hardware_blueprints/amr/clearpath-jackal.md)
and verify motor control before continuing.

## Install the Deployment Package

::::{tab-set}
:::{tab-item} **Jazzy**
:sync: jazzy

```bash
sudo apt update
sudo apt install ros-jazzy-wandering-jackal-tutorial
```

:::
:::{tab-item} **Humble**
:sync: humble

```bash
sudo apt update
sudo apt install ros-humble-wandering-jackal-tutorial
```

:::
::::

## Run the Deployment

Log in as the `administrator` user and run:

::::{tab-set}
:::{tab-item} **Jazzy**
:sync: jazzy

```bash
/opt/ros/jazzy/share/wandering_jackal_tutorial/scripts/wandering_jackal.sh
```

:::
:::{tab-item} **Humble**
:sync: humble

```bash
/opt/ros/humble/share/wandering_jackal_tutorial/scripts/wandering_jackal.sh
```

:::
::::

After startup, the robot begins exploring and RTAB-Map builds a map from the
RealSense camera input. Stop the workflow with `Ctrl-c`.

## Troubleshooting

For general robot issues, see the [troubleshooting guide](../../../resources/troubleshooting).