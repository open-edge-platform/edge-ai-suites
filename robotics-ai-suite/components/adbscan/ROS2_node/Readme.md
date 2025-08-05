# How to build the ADBSCAN ROS2 node locally
To build the package, type: `colcon build`.

# How to run the ADBSCAN ROS2 node
- To run with 2D lidar input, go to the /ADBSCAN_ROS2/src/ directory and type: `./start_adbscan_sub_2D.sh`
- To run with 3D lidar input, go to the /ADBSCAN_ROS2/src/ directory and type: `./start_adbscan_sub_3D.sh`
- To run with Realsense camera input, go to the /ADBSCAN_ROS2/src/ directory and type: `./start_adbscan_sub_RS.sh`

# ADBSCAN ROS2 node input description
The input data is passed into the ROS2 node through ROS2 topic defined in the ROS2 configuration file by parameter Lidar_topic; Edit this parameter for customized name. For 2D lidar input, the file name is `adbscan_sub_2D.yaml` and the message type is `sensor_msgs::msg::LaserScan`; For 3D lidar input, the file name is `adbscan_sub_3D.yaml` and the message type is `sensor_msgs::msg::PointCloud2`; For realsense input, the file name is `adbscan_sub_RS.yaml` and the message type is `sensor_msgs::msg::PointCloud2`; 

# ADBSCAN ROS2 node output description
The output is published to the ROS2 topic `obstacle_array`, and the message format is `nav2_dynamic_msgs::msg::ObstacleArray`.

# How to visualize the output in rviz
To visualize the output, please subscribe launch `rviz` and visualize the topic: `visualization_msgs/MarkerArray`.

