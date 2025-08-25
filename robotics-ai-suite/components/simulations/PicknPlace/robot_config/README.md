# Multi-Robot Framework for Gazebo
Welcome to the multi-robot launching framework for Gazebo. This framework facilitates the deployment of multiple robots within Gazebo, each encapsulated within its own unique namespace. At present, we provide support for two prominent robot types:

* AMRs (Autonomous Mobile Robots) based on the Turtlebot3 model.
* ARMs (Robotic Arms) designed around the UR5 model.

## Overview
The launching mechanism for the robots is orchestrated through launch.py. This allows for a modular approach wherein individual robots can be initiated using the **IncludeLaunchDescription** with their respective parameters.

## Usage
### AMR (Turtlebot3) Launching
To launch an AMR, the following code snippet can be used:
```
robot_config_path = get_package_share_directory('robot_config')
amr_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(robot_config_launch_dir, 'amr.launch.py')),
        launch_arguments={ 'amr_name': 'amr1',
                           'x_pos': '-0.1',
                           'y_pos': '-0.3',
                           'yaw': '3.14159',
                           'use_sim_time': use_sim_time,
                           'launch_stack': 'true',
                           'wait_on': 'service /spawn_entity'
                          }.items()
                        )

ld.add_action(amr_launch_cmd)
```

### ARM (UR5) Launching
For initiating an ARM, utilize the code below:
```
arm1_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(robot_config_launch_dir, 'arm.launch.py')),
        launch_arguments={ 'arm_name': 'arm1',
                           'x_pos': '0.18',
                           'y_pos': '0.0',
                           'yaw': '0.0',
                           'pedestal_height': '0.16',
                           'use_sim_time': use_sim_time,
                           'launch_stack': 'true',
                           'wait_on': 'topic /amr1/cmd_vel'
                          }.items()
                        )
ld.add_action(arm1_launch_cmd)
```

## Synchronization
The optional parameter, **wait_on**, facilitates the creation of a launch description that becomes active once a specific topic, action, or service is available. This feature is designed to ensure proper synchronization. To use it, provide the interface type followed by the interface name. 

## Gazebo Plugins
Included are two Gazebo plugins. The first derives from OSRF's implementation of a Conveyor Belt, while the second offers a service for clearing namespaces. This namespace clearance ensures consistent namespace management across different models.
