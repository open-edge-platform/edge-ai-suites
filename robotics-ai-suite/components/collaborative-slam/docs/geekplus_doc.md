### Background & Settings

Geekplus is a leading warehouse robotics company and we used to collaborate with them to improve localization accuracy and relocalization performance. During algorithm development, we are provided with ros bag files that captures the real-world warehouse environment. The bag files have two special settings of tf tree that are different from general datasets:

1. For up-view fisheye camrea, the tf tree only contains a node for **camera_link**, but doesn't contain a node for **image_frame**. Therefore, an extra parameter **T_image_to_camera** (```T_ic```) should be added to make the system work properly when odometry data is used.

2. The bag file contains a node on the tf tree named *map* which happens to be the same default name for **map_frame**. This *map* frame is a fixed frame that comes from Lidar. It may cause the rviz to show inconsistent results between tf tree and published pose calculated from SLAM.


### How to run geekplus dataset

For the up-view fisheye camera, the recommended commands are:

1) Construct the map

```shell
# Mapping (tracker)
ros2 launch univloc_tracker tracker_geek_fisheye.launch.py use_odom:=true

# Mapping (server)
ros2 launch univloc_server server_geek.launch.py fix_scale:=true save_map_path:=/path_for_saving_map/xx.msg save_traj_folder:=/path_for_saving_mapping_traj/
```

2) Load the map and run localization

```shell
# Localization (tracker)
ros2 launch univloc_tracker tracker_geek_fisheye.launch.py slam_mode:=localization id:=2 traj_store_path:=/path_for_saving_localization_traj/

# Localization (server)
ros2 launch univloc_server server_geek.launch.py server_mode:=localization fix_scale:=true load_map_path:=/path_for_saving_map/xx.msg
```


### Evaluation method for geekplus dataset

Note that the ground truth files are not included in the repo. You can find them in shared documents (named gt_new.zip). We can send you if needed.

- Any ground truth txt file ends with *-front* means using the front-view RealSense camera (stereo) and otherwise using the up-view fisheye camera (monocular).

- For the ground truth result, *kongkuang* data of sequence *gdata0730* is obtained using the transformation from frame ```odom``` to ```camera```, rather than from frame ```map``` to ```camera``` that is used in other data.

1) Evaluate the accuracy of the constructed map and save the transformation matrix

```shell
# evo_ape tum ground_truth mapping_traj
evo_ape tum ground_truth.txt /path_for_saving_mapping_traj/client0map0.txt -vap --save_results /path_for_saving_transformation/xx.zip
```

2) Use the transformation matrix from 1) and avoid the use of alignment method in evo tool (*-a* in evo_ape) when evaluating the localization result

```shell
# python3 align_pose.py ground_truth localization_traj transformation_matrix
python3 align_pose.py ground_truth.txt /path_for_saving_localization_traj/xx.txt /path_for_saving_transformation/xx.zip
```

You are expected to see the accuracy result (rmse in the unit of meter) in the terminal.
