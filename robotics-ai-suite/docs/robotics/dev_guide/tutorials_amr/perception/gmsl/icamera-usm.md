# GMSL Ingestion Guide icamera-usm


This tutorial will cover getting GMSL RGB camera stream working as a ros node. This tutorial expect that the user has completed [GMSL Guide](https://docs.openedgeplatform.intel.com/2026.0/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/index_gmslguide.html).


The current tested cameras for this tutorials are the following
[RealSense™ Depth Camera D457](https://www.realsenseai.com/products/d457-gmsl-fakra/) and
[D3CMCXXX-115-084](https://www.d3embedded.com/product/isx031-smart-camera-medium-fov-gmsl2-unsealed/).

The user can enable up to 6 camera stream of either four `D3CMCXXX-115-084` or 2x `RealSense™ Depth Camera D457` on a single CSI port. If the user can mix and match the cameras, for example putting 4 `D3CMCXXX-115-084` on CSI port 0, and two `RealSense™ Depth Camera D457` on CSI port 2.


## Validate Cameras

Execute the following command:

```bash
ls -la /dev/video-*
```

symbolic link of cameras should show up.

if the cameras are `RealSense™ Depth Camera D457` the result of the command should look like the following 

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

```bash
lrwxrwxrwx 1 root root 11 Jun 15 16:12 /dev/video-isx031-a-0 -> /dev/video1
lrwxrwxrwx 1 root root 11 Jun 15 16:12 /dev/video-isx031-b-0 -> /dev/video2
lrwxrwxrwx 1 root root 11 Jun 15 16:12 /dev/video-isx031-c-0 -> /dev/video3
lrwxrwxrwx 1 root root 11 Jun 15 16:12 /dev/video-isx031-d-0 -> /dev/video4
```
This one shows that I have four `D3CMCXXX-115-084` connected.


## Install icamera

```bash
sudo apt-get install ros2-jazzy-icamera-usm
```

## Start the ros2 icamera-usm node

The extra arg also enables classis ros raw image publish

```bash
ros2 run  icamera_usm icamera_usm_node --ros-args -p publish_image_raw:=true
```

expected output with 4 cameras running
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
```bash
source /opt/ros/jazzy/share/icamera_usm/generate_ai_models.sh --dest ~/test
```

## Run a sample inference pipeline
```bash
ros2 launch icamera_usm usm_multi.launch.py 
```

This example will only connect to a single camera, to connect to multiple camera you can run the following 

```bash
ros2 launch icamera_usm usm_multi.launch.py cameras:=camera0,camera1
```

The default the model that is being used is yolov8n.xml this is the smaller version of the model and is not as accurate.
Changing the model that will be used can be done with the following arg

```bash
ros2 launch icamera_usm usm_multi.launch.py cameras:=camera0,camera1 model:=$HOME/new_test/models/yolov8/FP16/yolov8n.xml 
```



Visualize the example. create a file called inference-visualize.rviz and add the following into it
```bash
vim inference-visualize.rviz
```
copy the following into it.

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

start rviz using the configuration file that was created

```bash
rviz2 -d inference-visualize.rviz
```

 user can visualize the inference by changeing `camera0` with `camera1..3` if there is more than one camera
