---
title: OpenVINO™ Yolov8 Tutorial
---

This tutorial serves as an example for understanding the utilization of
OpenVINO™ node. It outlines the steps for installing ROS 2 OpenVINO™
node and executing the segmentation model on the CPU, using a Intel®
RealSense™ camera image as the input.

# Getting Started

# Prerequisites

- [Prepare the target system](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/prepare-system.html)
- [Setup the Robotics AI Dev Kit APT Repositories](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/apt-setup.html)
- [Install OpenVINO™ Packages](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/install-openvino.html)
- [Install Robotics AI Dev Kit Deb packages](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/install.html)
- [Install the Intel® NPU Driver on Intel® Core™ Ultra Processors (if applicable)](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/install-npu-driver.html)

## Install OpenVINO™ package

Follow the instructions on [Install OpenVINO™ Packages](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/install-openvino.html) to install OpenVINO™.

## Install Python packages (optional)

Following Python packages are necessary to automatically download and
convert the model to IR files. Also You can provide your own model files
in the config, if you have them already.

> ``` 
> pip3 install numpy pandas openvino-dev ultralytics nncf onnx
> ```

## Install Deb package

> ``` 
> sudo apt install ros-humble-openvino-yolov8 ros-humble-openvino-yolov8-msgs
> ```

# Run Demo with Intel® RealSense™ Topic Input

First create a config file [pipeline.toml]{.title-ref}. If not present,
sample content for this configuration file (including the comments) will
be generated in the command output when executing the
`ros2 run yolo yolo` command.

> ``` 
> title = "Yolo Ros Node"
>
> [main]
> pipelines = ["pipeline1"] # names will be used to name output topics
> models = ["model1"]
>
> [model1]
> model_path = "" # if empty, model will be downloaded from ultralytics, otherwise provide path to .xml file or other format supported by openvino
> model_path_bin = "" # use only if you want to provide your own model in openvino format, and there you need to provide path to .bin file
> # following options are only used if model_path is empty
> task = "segmentation" # options: detection, segmentation, pose
> # w,h of internal resolution, input frames are resized
> # consider using smaller resolution for faster inference
> width = 640 
> height = 480
> model_size = "n" # options: n, s, m, l, x (refer to ultralytics docs)
> half = true # use half precision
>
>
> [pipeline1]
> model = "model1" # model name from [main] section
> device = "CPU"  # options CPU, GPU (this is directly passed to openvino)
> performance_mode = 1 # Performance mode 1=Latency, 2=Throughput, 3=Cumulative throughput
> priority = 1 # 0=Low, 1=Normal, 2=High
> precision = 1 #  0 = FP32, 1 = FP16 , this is passed as hint to openvino
> num_requests = 1 # Number of inference requests (hint for openvino) recommended 1 per input stream
> map_frame = "map" # setting is ignored if single topic is used, otherwise it will be used to synchronize camera location
> queue_size = 10
> workers = 2 # Aim for 2 workers per input stream
> max_fps = -1 # -1 for unlimited
> publish_video = true # publish video with detections
> publish_detections = true # publish detections (special message type), can be used to generate video with detections
> # use this if you don't have or don't need synchronized depth data
> rgb_topic = []
> rgb_topic_max_fps = [] # same length as rgb_topic, -1 for unlimited will assume -1 for all topics if not provided
> # depth is not used by yolo, but if provided this node will synchronize rgb and depth and transform to camera frame
> # this can be later used to place detections in 3D sSpace
> # topics need to be provided in pairs
> rgbd_topic_rgb = ["/camera/color/image_raw"]
> rgbd_topic_depth = ["/camera/depth/image_raw"]
> rgbd_topic_max_fps = []
> ```
>
> ``` 
> ros2 run yolo yolo --toml pipeline.toml &
> ros2 run realsense2_camera realsense2_camera_node --ros-args \
>             -p depth_module.profile:=640x480x60 \
>             -p rgb_camera.profile:=640x480x60 \
>             -p align_depth.enable:=True \
>             -r /camera/camera/color/image_raw:=/camera/color/image_raw \
>             -r /camera/camera/color/camera_info:=/camera/color/camera_info \
>             -r /camera/camera/aligned_depth_to_color/image_raw:=/camera/depth/image_raw \
>             -r /camera/camera/aligned_depth_to_color/camera_info:=/camera/depth/camera_info 
> ```

Once you start the node, you view the output video and detections using
the following command:

> ``` 
> rviz2 
> ```

Then you can subscribe to the `/pipeline1/color/image_raw/yolo_video`
topic to view the result.

# Advanced usage

Besides generating a video, this node is also capable of providing the
number of post processed detections. Detections are published on a topic
`<pipeline_name>/<rgb_topic>/yolo_frame`. For example for above
configuration it would be `pipeline1/color/image_raw/yolo_frame`.

The messages have following structure:

> ``` 
> std_msgs/Header header # Header timestamp should be acquisition time of image
>
> sensor_msgs/Image rgb_image # Original image
> sensor_msgs/Image depth_image # only if topic depth is provided
>
> string task # "Detection" "Segmentation "Pose" 
>
> geometry_msgs/TransformStamped camera_transform # Camera transform captured at the time of image arrival
>
> YoloDetection[] detections # Array of detections
> ```

Structure of the YoloDetection message object:

> ``` 
> float32 confidence
>
> # Coordinates of bounding box
> uint32 x
> uint32 y
> uint32 height
> uint32 width
>
> string class_name
>
> # Only used for Pose task
> float32[] pose_xy #  X,Y of joints in image coordinates (17 total)
> float32[] pose_visible # Probability of joint being visible
>
> # Only used for Segmentation task, this is flatten array of mask, same size as bounding box
> float32[] mask
> ```

The same message structure is used for all 3 tasks (detection,
segmentation, pose) with some fields being empty when not used.

For body pose related tasks there is an image that helps in
understanding the meaning of joints and how they are connected. ..
Connected Joints (Research gate)
<https://www.researchgate.net/figure/Key-points-for-human-poses-according-to-the-COCO-output-format-R-L-right-left_fig3_353746430>

# Other considerations

Yolov8 model requires a commercial license from Ultralytics. This
package only provides an efficient way to run the model on OpenVINO™
with ROS 2. Models and weights are downloaded from ultralytics and
converted to IR format.

This package requires the model to have fixed shape, and to have 80
classes (for detection/segmentation). Keep this in mind when providing
fine tuned models.

Automatic downloading of INT8 models is only supported for square input
shapes and only for detection task. This is a limitation of
ultralytics/nncf library. Therefore if you posses an quantized model for
another task or resolution you can still use it.

Resolution of input images (coming from ROS 2 topic) is not tied to the
input resolution of the model. In case of size mismatch bicubic
interpolation is used. At the same time outputs of the models are also
scaled back to original image size. You can leverage this to take
advantage of larger models as they provide more stable detection.

Something that might be also useful is to play with performance_mode and
inference requests, count to get the best balance between latency and
throughput. The code is optimized to in such a way that if no major
hiccups are present using throughput mode will provide the best of both
worlds.
