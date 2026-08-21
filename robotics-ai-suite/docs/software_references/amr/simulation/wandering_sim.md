# Simulating `wandering`

In this software reference, you'll simulate the `wandering` pipeline. This pipeline is built of multiple components available in the Robotics AI Suite, showcasing how to simulate a complex perception and navigation workload in Gazebo.

`wandering` is a fully-autonomous robotics pipeline, allowing a robot to map the space around it and actually navigate to make sure its map is complete, all without human intervention. You can consider it as a demonstration of what combining multiple ingredients from Intel Robotics AI Suite can create out of the box, and give you an idea of how you can use them in your own robotics use-case.

## Architecture

Wandering combines sensor input, SLAM and mapping, navigation, and robot control.
It continuously updates an occupancy map, chooses unexplored frontiers, and
sends navigation goals through Nav2 while avoiding obstacles identified by the
perception pipeline.

## Components

- RTAB-Map creates and updates the environment map.
- Nav2 plans and executes movement toward exploration goals.
- `WanderingMapper` selects unexplored frontiers.
- `GoalCatcher` sends `NavigateToPose` goals to Nav2.

## Source Code

The [Wandering source code](https://github.com/open-edge-platform/edge-ai-suites/tree/main/robotics-ai-suite/components/wandering)
is available with the Robotics AI Suite.

## Run the Gazebo Simulation

```{include} includes/wandering-gazebo-waffle.md
:start-line: 2
```

## Next Steps

You've completed the simulation-focused software references. Continue to the
[deployment learning path](../deployment/index.md) to run the
Wandering workflow on a physical robot.