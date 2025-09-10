# Robotics AI Suite

**NOTE**: Robotics AI Suite is currently a preview release! A formal release will follow shortly.

## Description
Robotics AI Suite is a preview collection of robotics applications, libraries, samples, and benchmarking tools to help developers build solutions faster. It includes models and pipelines optimized with the OpenVINO™ toolkit for accelerated performance on Intel® CPUs, integrated GPUs, and NPUs. Detailed user guide and documentation can be found here: [Robotics AI Suite](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/index.html).

## Collection
Collections organize workflows and capabilities for three robot categories—stationary robots, autonomous mobile robots (AMRs), and humanoids. Each collection brings together libraries for core robotics workloads, robotics control recipes, and virtualization/application management, with ROS 2 integration points, supported sensor profiles, and repeatable benchmarking. They also include OpenVINO™ toolkit–optimized models across computer vision, large language models (LLMs), and vision-language-action (VLA) to accelerate inference on Intel® CPUs, integrated GPUs, and NPUs, helping teams evaluate, assemble, and scale solutions faster.

**Humanoid - Imitation Learning:**

| Application | Documentation | Description |
| ----------- | ------------- | ----------- |
| [Diffusion Policy (OpenVINO)](pipelines/diffusion-policy-ov) | [Diffusion Policy (OpenVINO)](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/sample_pipelines/diffusion_policy.html) | Diffusion Policy implementation optimized with Intel OpenVINO toolkit |
| [Imitation Learning - ACT](pipelines/act-sample) | [Imitation Learning - ACT](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/sample_pipelines/imitation_learning_act.html) | Imitation learning pipeline using Action Chunking with Transformers(ACT) algorithm to train and evaluate in simulator or real robot environment with Intel® optimization |
| [Improved 3D Diffusion Policy (OpenVINO)](pipelines/idp3-ov) | [Improved 3D Diffusion Policy (OpenVINO)](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials/model_idp3.html) | Improved 3D Diffusion Policy implementation optimized with Intel OpenVINO toolkit |
| [LLM Robotics Demo](pipelines/llm-robotics-demo) | [LLM Robotics Demo](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/sample_pipelines/llm_robotics.html) | This tutorial provides a step-by-step guide to set up a real-time system to control a JAKA robot arm with movement commands generated using an LLM |
| [Robotics Diffusion Transformer (OpenVINO)](pipelines/rdt-ov) | [Robotics Diffusion Transformer (OpenVINO)](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/sample_pipelines/robotics_diffusion_transformer.html) | Robotics Diffusion Transformer implementation optimized with Intel OpenVINO toolkit |
| [VSLAM: ORB-SLAM3](pipelines/orb-slam3-sample) | [VSLAM: ORB-SLAM3](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/sample_pipelines/ORB_VSLAM.html) | One of the popular real-time feature-based SLAM libraries able to perform Visual, Visual-Inertial and Multi-Map SLAM with monocular, stereo and RGB-D cameras, using pin-hole and fisheye lens models |

**Autonomous Mobile Robot:**

| Algorithm | Documentation | Description |
| ----------| ------------- | ----------- |
| [ADBScan](components/adbscan) | [ADBScan](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/navigation/adbscan/index.html) | ADBSCAN (Adaptive DBSCAN) is an Intel-patented algorithm. It is a highly adaptive and scalable object detection and localization (clustering) algorithm, tested successfully to detect objects at all ranges for 2D Lidar, 3D Lidar, and Intel® RealSense™ depth camera. |
| [Collaborative-SLAM](components/collaborative-slam) | [Collaborative-SLAM](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/navigation/collaborative-slam.html) | Collaborative Visual SLAM example which is compiled natively for both Intel® Core™ and Intel® Atom® processor-based systems. In addition, GPU acceleration may be enabled on selected Intel® Core™ processor-based system. |
| [Fastmapping](components/fast-mapping) | [Fastmapping](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/navigation/run-fastmapping-algorithm.html) |
| [GroundFloor Segmentation](components/groundfloor) | [GroundFloor Segmentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/perception/pointcloud-groundfloor-segmentation.html) | Showcases an Intel® algorithm designed for the segmentation of depth sensor data, compatible with 3D LiDAR or a Intel® RealSense™ camera inputs |
| [ITS-Planner](components/its-planner) | [ITS-Planner](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/navigation/its-path-planner-plugin.html) | Intelligent Sampling and Two-Way Search (ITS) global path planner is an Intel® patented algorithm. ITS is a new search approach based on two-way path planning and intelligent sampling, which reduces the compute time by about 20x-30x on a 1000 nodes map comparing with the A* search algorithm. |
| [Multi-Camera-Demo](components/multicam-demo) | [Multicam-Demo](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/perception/openvino/pyrealsense2_d457_multicam_object_detection_tutorial.html) | Multi-camera use case is demonstrated using an Axiomtek Robox500 ROS2 AMR Controller and four Intel® RealSense™ Depth Camera D457 |
| [Object Detection](components/object-detection) | [Object Detection](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/perception/openvino/object_detection_tutorial.html) | Example for understanding the utilization of the ROS 2 node with OpenVINO™ toolkit. It outlines the steps for installing the node and executing the object detection model. |
| [Simulations](components/simulations) | [Simulations](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/simulation/index.html) | Tutorials that show how to use the ROS 2 simulations with Intel® Robotics AI Dev Kit. Robot sensing and navigation can be tested in these simulated environments. |
| [Wandering](components/wandering) | [Wandering](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/navigation/wandering_app/index.html) | The Wandering mobile robot application is a Robot Operating System 2 (ROS 2) sample application. It can be used with different SLAM algorithms in combination with the ROS2 navigation stack, to move the robot around in an unknown environment. The goal is to create a navigation map of the environment. |

**Stationary Robot Vision & Control:**

| Application | Documentation | Description |
| ------------| ------------- | ----------- |
| [Stationary Robot Vision & Control](robot-vision-control) | [Stationary Robot Vision & Control](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/rvc/index.html) | Robot Vision and Control is a robotic software framework aimed at tackling Pick and place, Track and place industrial problems. Under active development, hence released in *pre-release* quality |

**Intel® OpenVINO™ toolkit optimized model algorithms:**

| Algorithm | Description |
| --------- | ----------- |
| [YOLOv8](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials.html#model-tutorials) | CNN based object detection |
| [YOLOv12](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials.html#model-tutorials) | CNN based object detection |
| [MobileNetV2](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials.html#model-tutorials) | CNN based object detection |
| [SAM](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials.html#model-tutorials) | Transformer based segmentation |
| [SAM2](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials.html#model-tutorials) | Extend SAM to video segmentation and object tracking with cross attention to memory |
| [FastSAM](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials.html#model-tutorials) | Lightweight substitute to SAM |
| [MobileSAM](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials.html#model-tutorials) | Lightweight substitute to SAM (Same model architecture with SAM. Refer to OpenVINO toolkit and Segment Anything Model (SAM) tutorials for model export and application) |
| [U-NET](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials.html#model-tutorials) | CNN-based segmentation and diffusion model |
| [DETR](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials.html#model-tutorials) | Transformer-based object detection |
| [DETR GroundingDino](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials.html#model-tutorials) | Transformer based object detection |
| [CLIP](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials.html#model-tutorials) | Transformer-based image classification |
| [Action Chunking with Transformers - ACT](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials/model_act.html#model-act) | An end-to-end imitation learning model designed for fine manipulation tasks in robotics |
| [Feature Extraction Model: SuperPoint](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials/model_superpoint.html#model-superpoint) | A self-supervised framework for interest point detection and description in images, suitable for a large number of multiple-view geometry problems in computer vision |
| [Feature Tracking Model: LightGlue](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials/model_lightglue.html#model-lightglue) | A model designed for efficient and accurate feature matching in computer vision tasks |
| [Bird’s Eye View Perception: Fast-BEV](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials/model_fastbev.html#model-fastbev) | Obtaining a Bird's Eye View (BEV) perception is to gain a comprehensive understanding of the spatial layout and relationships between objects in a scene |
| [Monocular Depth Estimation: Depth Anything V2](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials/model_depthanythingv2.html#model-depthanythingv2) | A powerful tool that leverages deep learning to infer 3D information from 2D images |

