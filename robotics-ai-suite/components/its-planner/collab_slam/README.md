# Enable Collaborative Visual SLAM Framework on ROS2 Navigation

The Collaborative Visual SLAM Framework can be obtained from [here](https://github.com/open-edge-platform/edge-ai-suites)

Here are the instructions on how to enable Collaborative Visual SLAM Framework on ROS2 Navigation package

1. Get the Collaborative Visual SLAM code

    `git clone --recursive https://github.com/open-edge-platform/edge-ai-suites`

2. Build the collaborative VSLAM, nav2_bringup and the ITS planner

    `source /opt/ros/humble/setup.bash`

    `colcon build`
    
    `source install/setup.bash`

3. Run the Collab SLAM ROS2 Navigation

    To run in the localization mode: `./run_collab.sh localization`

    To run in the mapping mode: `./run_collab.sh mapping`
