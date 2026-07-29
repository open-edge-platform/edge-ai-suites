<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# GMSL Ingestion Guide icamera-usm


This tutorial will cover getting GMSL RGB camera stream working as a ROS node to enable quick ingest of GMSL RBG Camera streams. This tutorial expect that the user has completed [GMSL Guide](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/index_gmslguide.html).


The current tested cameras for this tutorials are the following
[RealSense™ Depth Camera D457](https://www.realsenseai.com/products/d457-gmsl-fakra/) and
[D3CMCXXX-115-084](https://www.d3embedded.com/product/isx031-smart-camera-medium-fov-gmsl2-unsealed/).

You can enable up to 6 camera streams of either four `D3CMCXXX-115-084` or 2x `RealSense™ Depth Camera D457` on a single CSI port. You can mix and match the cameras as well, for example putting 4 `D3CMCXXX-115-084` on CSI port 0, and two `RealSense™ Depth Camera D457` on CSI port 2.


## Validate Cameras

Execute the following command:

```bash
ls -la /dev/video-*
```

This should show simplified name symbolic links pointing to the original device files.

If the cameras are `RealSense™ Depth Camera D457` the result of the command should look like the following:

```bash
lrwxrwxrwx 1 root root 11 Jun 15 15:49 /dev/video-rs-color-0 -> /dev/video2
lrwxrwxrwx 1 root root 11 Jun 15 15:49 /dev/video-rs-color-1 -> /dev/video8
lrwxrwxrwx 1 root root 11 Jun 15 15:49 /dev/video-rs-color-md-0 -> /dev/video3
lrwxrwxrwx 1 root root 11 Jun 15 15:49 /dev/video-rs-color-md-1 -> /dev/video9
lrwxrwxrwx 1 root root 11 Jun 15 15:49 /dev/video-rs-depth-0 -> /dev/video0
lrwxrwxrwx 1 root root 11 Jun 15 15:49 /dev/video-rs-depth-1 -> /dev/video6
lrwxrwxrwx 1 root root 11 Jun 15 15:49 /dev/video-rs-depth-md-0 -> /dev/video1
lrwxrwxrwx 1 root root 11 Jun 15 15:49 /dev/video-rs-depth-md-1 -> /dev/video7
lrwxrwxrwx 1 root root 11 Jun 15 15:49 /dev/video-rs-imu-0 -> /dev/video5
lrwxrwxrwx 1 root root 12 Jun 15 15:49 /dev/video-rs-imu-1 -> /dev/video11
lrwxrwxrwx 1 root root 11 Jun 15 15:49 /dev/video-rs-ir-0 -> /dev/video4
lrwxrwxrwx 1 root root 12 Jun 15 15:49 /dev/video-rs-ir-1 -> /dev/video10
```
Here it shows there are two `RealSense™ Depth Camera D457` connected, 0, and 1 with all of there sensors showing up.

If using the `D3CMCXXX-115-084`, the output will look like the following:

```bash
lrwxrwxrwx 1 root root 11 Jun 15 16:12 /dev/video-isx031-a-0 -> /dev/video1
lrwxrwxrwx 1 root root 11 Jun 15 16:12 /dev/video-isx031-b-0 -> /dev/video2
lrwxrwxrwx 1 root root 11 Jun 15 16:12 /dev/video-isx031-c-0 -> /dev/video3
lrwxrwxrwx 1 root root 11 Jun 15 16:12 /dev/video-isx031-d-0 -> /dev/video4
```
This one shows that there are four `D3CMCXXX-115-084` connected.


## Install icamera

```bash
sudo apt-get install ros2-$ROS_DISTRO-icamera-usm
```

## Start the ROS2 icamera-usm node

The following command launches the GMSL cameras using classical ROS2 raw image publish along with shared memory.

```bash
ros2 run  icamera_usm icamera_usm_node --ros-args -p publish_image_raw:=true
```

This will find all the available GMSL cameras that are identified and setup by the driver, and binded. In the following log you can see there are four cameras connected. 'a' to 'd' represents the different cameras, and value '0' represents the CSI port that they are connected to.
```bash
[INFO] [1781565274.914167474] [icamera_usm]: [isx031 a-0] V4L2 MMAP ready: 4 bufs, fmt=UYVY 1920x1536
[INFO] [1781565274.914342851] [icamera_usm]: [isx031 a-0] V4L2 capture started (UYVY 1920x1536)
[INFO] [1781565274.914361840] [icamera_usm]: [isx031 b-0] device=/dev/video-isx031-b-0 fmt=UYVY 1920x1536 (discovered fourcc was 'UYVY')
[INFO] [1781565274.961423730] [icamera_usm]: [isx031 b-0] V4L2 MMAP ready: 4 bufs, fmt=UYVY 1920x1536
[INFO] [1781565274.961475486] [icamera_usm]: [isx031 b-0] V4L2 capture started (UYVY 1920x1536)
[INFO] [1781565274.961488312] [icamera_usm]: [isx031 c-0] device=/dev/video-isx031-c-0 fmt=UYVY 1920x1536 (discovered fourcc was 'UYVY')
[INFO] [1781565275.008815292] [icamera_usm]: [isx031 c-0] V4L2 MMAP ready: 4 bufs, fmt=UYVY 1920x1536
[INFO] [1781565275.008859167] [icamera_usm]: [isx031 c-0] V4L2 capture started (UYVY 1920x1536)
[INFO] [1781565275.008866859] [icamera_usm]: [isx031 d-0] device=/dev/video-isx031-d-0 fmt=UYVY 1920x1536 (discovered fourcc was 'UYVY')
[INFO] [1781565275.066832723] [icamera_usm]: [isx031 d-0] V4L2 MMAP ready: 4 bufs, fmt=UYVY 1920x1536
[INFO] [1781565275.066949812] [icamera_usm]: [isx031 d-0] V4L2 capture started (UYVY 1920x1536)
[INFO] [1781565275.066956796] [icamera_usm]: on_activate: all pipelines running
```

## Download the models

To run a example that uses the shared memory or legacy which uses the classical publish, you will need to first download the yolov8 models. The following script will download the models and place them in the destination folder using the `--dest` flag.

```bash
source /opt/ros/$ROS_DISTRO/share/icamera_usm/generate_ai_models.sh --dest ~/test
```

## Run a sample inference pipeline
```bash
ros2 launch icamera_usm usm_multi.launch.py
```
By default the example only connectes to `camera0` to inference on multiple cameras use the following command. The user will add extra argument `cameras` followed by the extra cameras `camera0` to `cameraX`. To identify what camera streams are available execute `ros2 topic list`, this will show all the published topics. Topics for camera start with the namespace `/icamera`

```bash
ros2 launch icamera_usm usm_multi.launch.py cameras:=camera0,camera1
```
The default model `YOLOv8n` is a smaller model and is not as accurate, if you are not getting the results you expect then change the model that is being used.
There are three models downloaded with the `generate_ai_models.sh` script: `yolov8n`,`yolov8s`, `yolov8m`.

You can change the model they would like to use bu using the extra arg `model`. The following example provides the same model with the extra arg:

```bash
ros2 launch icamera_usm usm_multi.launch.py cameras:=camera0,camera1 model:=$HOME/new_test/models/yolov8/FP16/yolov8n.xml
```

You can use RVIZ to visualize the output of the inference. First create a new RVIZ file using `vim`:

```bash
vim inference-visualize.rviz
```
Copy the following configuration into `inference-visualize.rviz`:

```yaml
Panels:
  - Class: rviz_common/Displays
    Name: Displays
  - Class: rviz_common/Views
    Name: Views
Visualization Manager:
  Class: ""
  Displays:
    - Class: rviz_default_plugins/Image
      Name: Legacy Annotations
      Enabled: true
      Topic:
        Value: /legacy/camera0/annotated_image
        Reliability Policy: Best Effort
        History Policy: Keep Last
        Depth: 1
      Normalize Range: false
    - Class: rviz_default_plugins/Image
      Name: USM Annotations
      Enabled: true
      Topic:
        Value: /infer_usm/camera0/image_annotated
        Reliability Policy: Best Effort
        History Policy: Keep Last
        Depth: 1
      Normalize Range: false
  Global Options:
    Background Color: 48; 48; 48
    Fixed Frame: camera
  Tools:
    - Class: rviz_default_plugins/MoveCamera
  Value: true
  Views:
    Current:
      Class: rviz_default_plugins/Orbit
      Name: Orbit
    Saved: ~
Window Geometry:
  Height: 720
  Width: 1280
  Hide Left Dock: false
  Hide Right Dock: false
```

Launch rviz using the following command:

```bash
rviz2 -d inference-visualize.rviz
```

You can control what camera to visualize by modifying the  `Topic` value `Value: /infer_usm/camera0/image_annotated` to `Value: /infer_usm/camera1/image_annotated`
