# RVC (Robot Vision & Control)

Exemplary code and configuration for two uses cases:

- Dynamic tracking of AI based object detection using Universal Robot UR5e
- Static tracking of computer vision detection using direct pendant control of UR5e

## Interactive development using VSCode and DevContainer

### Prerequisites

Installed and properly configured tools:

- Visual Studio Code
- Docker

### Build & develop

- Start *Visual Studio Code*
- Open *rvc* folder (this file's parent folder) as DevContainer

- Run provided tasks, e.g. the *Build task* ( with Ctrl + Shift + B )

### Run examples

To execute the demos, run respectively:

- ros2 launch rvc_dynamic_motion_controller_use_case dynamic_demo_launch.py robot_ip:=<robot_ip>
- ros2 launch rvc_static_motion_controller_use_case static_demo_launch.py robot_ip:=<robot_ip>
