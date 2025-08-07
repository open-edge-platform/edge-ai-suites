### Robot setup
Use Segway Robot as an example:

- Startup: Make sure the wire connections for power and communication are correct. Meanwhile fully charge the robot before using.

- Power supply for NUC/ Developing Board: You can either choose the circuit board on the robot or an external power bank to supply the power.

- RealSense Placement: Manually stick on the robot or use a bracket to place the camera. **Avoid any conductive surface on the robot to get in touch with the camera.**


### How to Build

#### Segway robot

```
cd YOUR_COLCON_WORKSPACE/src
# place repos under the src folder
cd ..
source /opt/ros/humble/setup.bash
# first build segway_msg
colcon build --packages-select segway_msg
# then build segwayrmp
colcon build --packages-select segwayrmp
```


#### RealSense

Follow the [instructions for ros-realsense setup](https://github.com/IntelRealSense/realsense-ros/tree/ros2) and we choose the method 2 to build.

To test the connection, you can use commands like ```dmesg``` or ```lsusb```. You may further verify using ```realsense-viewer```. If you encounter unstable RealSense connection, you can try to use a different connection line.


#### FastMapping

Follow the [Readme](../../fast-mapping/) to build. Note that Fast mapping does not have all needed parameters exposed. Following parameters should be changed in the code and re-compiled:
```
"depth_noise_factor": "0.08",
# Change the below number according to your robot
robot_radius_around_camera": "0.3"
```


#### Navigation
Follow the [github readme](https://github.com/ros-planning/navigation2/tree/main/nav2_bringup) and [installation guide](https://navigation.ros.org/getting_started/index.html#installation) to build. 

The default navigation param file is located [here](https://github.com/ros-planning/navigation2/tree/main/nav2_bringup/params) for reference. We also include ours in the doc folder. **Note that ```robot_radius``` parameter should be changed to the setting of your robot.**



### How to Run

First, start the robot, we use Segway Robot as an example:
```
# in the first terminal
ros2 run segwayrmp SmartCar
# in the second terminal
ros2 run segwayrmp drive_segway_sample
```
In the second terminal, press ```c``` to clear emergency stop state, then press ```e``` for chassis enable switch. Now the robot is ready to move, just press ```ctrl-c``` to stop the above two ros2 nodes.

Then, launch the full-stack launch file to start the system. Here are some explanations for the launch file:

- generate_segway_description: **Remember to change this part according to your robot.**
- static_tf: the origin and coordinate definition of the robot should be first determined. In our case, the origin of the robot is located at the center of the two wheels and the ground plane is where the value of z axis equals to 0. The x axis points to the front direction, the y axis points to the left direction and the z axis points to the up direction of the robot. **Remember to change the values according to your robot and the location of the camera.**
- device_type: set the type according to the camera you use (we use RealSense D435, so choose d435)
- initial_reset: it is recommended to set to true, which will allow the RealSense to reset on every start.
- fix_scale: it should set to true when using RGBD camera_setup and the scale will not be optimized during optimization.
- nav_params_file: For Segway robot, we use the same navigation param file as Pengo robot (pengo_nav.param.yaml).


To run the system, here are the recommended commands:

```
# Copy the launch file to the install folder of a package, for example to the univloc_tracker package
cp collab_slam.launch.py YOUR_COLCON_WORKSPACE/install/univloc_tracker/share/univloc_tracker/launch/

cd YOUR_COLCON_WORKSPACE
source install/setup.bash
# Change univloc_tracker to your package name
# Need to specify the navigation param you used
ros2 launch univloc_tracker collab_slam.launch.py nav_params_file:=/path_to_customized_nav_param/your_robot_nav.param.yaml
```

 After the system is fully launched, you can send a navigation goal to the robot on the rviz window and the robot is expected to move the desired destination.
