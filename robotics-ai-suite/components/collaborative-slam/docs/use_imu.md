### How to run the system with imu data


**EuRoC dataset**

```shell
# Tracker (choose one from the following two cases)
# Case1: Monocular input with IMU data
ros2 launch univloc_tracker euroc_mono.launch.py camera_setup:=Monocular_Inertial publish_tf:=false clean_keyframe:=true

# Case2: Stereo input with IMU data
ros2 launch univloc_tracker euroc_stereo.launch.py camera_setup:=Stereo_Inertial publish_tf:=false clean_keyframe:=true

# Server
ros2 launch univloc_server server.launch.py fix_scale:=true correct_loop:=false

# Play rosbag
ros2 bag play xxx
```

Explanations for the flags:

- `clean_keyframe`: whether to clean redundant keyframes in the map database. The performance may vary between sequences in EuRoC dataset when setting clean_keyframe as true or false.
- `fix_scale`: whether to fix scale during server optimization. If imu data is used, then `fix_scale` is always true since absolute scale can be obtained either by imu (Monocular_Inertial), or by depth or stereo camera (RGBD_Inertial, Stereo_Inertial).
- `correct_loop`: whether to enable loop correction in server. The performance may vary between sequences in EuRoC dataset when setting correct_loop as true or false.


**OpenLORIS dataset (RGBD input)**

```shell
# Tracker
# Please change the value of camera_fps that represents the real FPS of input camera images, the default value is 30.0 if you don't specify it
ros2 launch univloc_tracker tracker.launch.py camera:=d400 publish_tf:=false queue_size:=0 camera_setup:=RGBD_Inertial get_camera_extrin_from_tf:=false accel_topic:=/d400/accel/sample gyro_topic:=/d400/gyro/sample camera_fps:=30.0

# Server
ros2 launch univloc_server server.launch.py fix_scale:=true correct_loop:=false

# Play rosbag
ros2 bag play xxx
```

Explanations for the flags:

- `get_camera_extrin_from_tf`: whether to get camera extrinsic matrix from tf. Since OpenLORIS dataset cannot obtain extrinsic matrix, set to false to avoid unnecessary waiting.


**Self-recorded Dataset**

You need to provide the following imu-related parameters to the system:

1. Transform between camera and imu: `get_imu_extrin_from_tf` is used to control whether to obtain from tf or enter the values directly in tracker.yaml. When set to true, you must provide the correct `imu_frame` and `image_frame` from tf tree; When set to false, put the values into `tf_camera_imu`.

2. Feeding imu data (two ways are supported): 1) Providing the topic of `imu_topic` if accel and gyro data are already combined into one single topic; 2) Providing both the topics of `accel_topic` and `gyro_topic` if accel and gyro data are separated topics.

3. Parameters of IMU sensor: the below three params should be obtained from the manufacturer of sensor. Note that tracker.yaml provides default values for RealSense D435i camera. If you are not able to obtain these values, you can use the default ones.
- `imu_frequency`
- `imu_noise`
- `imu_bias_walker`

### Limitations

- RGBD_Inertial mode is not extensively tested yet, only verified on OpenLORIS market dataset.
