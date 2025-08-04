# Intel's Robotics AI Suite : Follow-me with gesture-control

This release version contains `debian` package building rules. `dpkg-buildpackage` is automatically triggered in the CI/CD pipeline and the created debian packages are pushed to Intel's AMR repo.

## Prerequisites

Please make sure to include intel's AMR repo to `/etc/apt/sources.list.d/`

### Install debian packages

Install `ros-humble-followme-turtlebot3-gazebo` debian package

```bash
sudo apt update
sudo apt install ros-humble-followme-turtlebot3-gazebo
```

### Install python modules

This application uses [Mediapipe Hands Framework](https://mediapipe.readthedocs.io/en/latest/solutions/hands.html) for hand gesture recognition. Please install the following python packages as a pre-requisite

```bash
pip3 install mediapipe
pip3 install numpy==1.24.3
```

## Run gazebo simulator with 2D lidar

```bash
sudo chmod +x /opt/ros/humble/share/followme_turtlebot3_gazebo/scripts/demo_lidar.sh
/opt/ros/humble/share/followme_turtlebot3_gazebo/scripts/demo_lidar.sh
```

## Run gazebo simulator with RealSense

Open three terminals and run the following commands
Terminal 1: This command will open gazebo simulator and rviz

```bash
sudo chmod +x /opt/ros/humble/share/followme_turtlebot3_gazebo/scripts/demo_RS.sh
/opt/ros/humble/share/followme_turtlebot3_gazebo/scripts/demo_RS.sh
```

Terminal 2:  This command will run the adbscan package

```bash
source /opt/ros/humble/setup.bash 
ros2 run adbscan_ros2_follow_me adbscan_sub_w_gesture --ros-args --params-file /opt/ros/humble/share/adbscan_ros2_follow_me/config/adbscan_sub_RS.yaml -r cmd_vel:=tb3/cmd_vel
 ```  

Terminal 3: This command will run the gesture recognition package

```bash
source /opt/ros/humble/setup.bash 
ros2 run gesture_recognition_pkg traj_and_img_publisher_node.py --ros-args --params-file /opt/ros/humble/share/gesture_recognition_pkg/config/gesture_recognition.yaml
 ```

## Robotic SDK 2023.1 Release: Follow-me

## Hardware

1. Turn off Pengo;
2. Unplug HDMI cable and replace with dungo;
3. Unplug power cable and replace it with battery;
4. Turn on the robot by pressing the switch button;

To check if RealSense camera is working, type:
realsense-viewer

## To Run Follow-me on Pengo with RealSense

note: the Kobuki chassis needs to be turned on for the motor to run.

Step 1: Enable Kobuki (only needed when moving the actual Pengo robot chassis’s Kobuki chassis):
cd /home/awm/project/robotic/ati/iotg_workloads-robotic_platform_poc
source ./setup.sh
./run_kobuki.sh

Step 2: Start RealSense ROS2 publication:

1. . /opt/ros/foxy/setup.sh
2. ros2 launch realsense2_camera rs_launch.py serial_no:="_109622074344" depth_module.profile:=640x480x6 pointcloud.enable:=true camera_namespace:=/

Step 3: To run RealSense version of Follow-me:
cd /home/awm/project/robotic/ati/Follow_me_demo/Follow_me_configurable_2/src
. ./install/setup.sh
./start_adbscan_sub_RS.sh

## To Run Follow-me on Pengo with 2D lidar

note: the Kobuki chassis needs to be turned on for the motor to run.

Step 1: Enable Kobuki (only needed when moving the actual Pengo robot chassis’s Kobuki chassis):
cd /home/awm/project/robotic/ati/iotg_workloads-robotic_platform_poc
source ./setup.sh
./run_pengo_lslam.sh

Step 2: To run RealSense version of Follow-me:
cd /home/awm/project/robotic/ati/Follow_me_demo/Follow_me_configurable_2/src
. ./install/setup.sh
./start_adbscan_sub_2.sh

## To configure

The configuration file for 2D lidar version is: adbscan_sub_2D.yaml
The configuration file for RealSense camera version is: adbscan_sub_RS.yaml

Parameters such as subsample ratio, filter range, sensor type etc. can be configured in this file.  
