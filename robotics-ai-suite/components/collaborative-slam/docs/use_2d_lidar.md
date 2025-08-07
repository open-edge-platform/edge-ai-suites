### Basic Logic using Lidar

**Lidar Pipeline**
The overall idea of incorporating lidar data into our system is to improve both the performance and functional safety and reliability with redundancy of additional data that the lidar provides in addition to visual information. Currently, we have implemented the Lidar support in the front-end (i.e. motion only bundle adjustment).  We plan to support lidar data in the back-end on the future releases to fully enable the lidar on the entire pipeline.

### How to enable 2D lidar support
In the `tracker.yaml` file, the extrinsic transformation matrix of the lidar location with respect to the robot base must be known.  Once, this matrix is added in the `yaml` file, the `use_lidar` flag should be set to `true` to enable the lidar.

Main parameters to be set:


| Parameter                     | Description                                                                                 | Type   | Default Value | Unit   |
|-------------------------------|---------------------------------------------------------------------------------------------|--------|---------------|--------|
| use_lidar            | Flag to enable/disable lidar support                                                         | bool   | false         | -      |
| tf_base_lidar               | The transformation matrix between base_link to Lidar. This extrinsic transformation matrix needs to be measured manually or by a calibration method from manufacturer                                                       | translation/quaternion | -           | meters |
| get_lidar_extrin_from_tf                   | Whether to get lidar extrinsics (w.r.t. robot base) from /tf or not                                                                  | bool | false          | - |
| lidar_height                      | The location of the lidar on the physical robot with respect to ground                                                  | double | 0.22      | meters |


### How to run the system with lidar data

**Example with RGBD dataset**

```shell
# Tracker
# Please change the value of camera_fps that represents the real FPS of input camera images, the default value is 30.0 if you don't specify it
 ros2 launch univloc_tracker tracker.launch.py rviz:=false gui:=true queue_size:=0 publish_tf:=false camera:=camera image_frame:=camera_color_optical_frame slam_mode:=mapping log_level:=warning camera_setup:=RGBD camera_fps:=30.0

# Server
ros2 launch univloc_server server.launch.py rviz:=false correct_loop:=true

# Play rosbag
ros2 bag play xxx
```

### Limitations

2D lidar support is not extensively tested yet and it only supports front-end at this time.