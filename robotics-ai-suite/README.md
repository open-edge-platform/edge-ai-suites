# Robotics AI Suite

The **Robotics AI Suite** is a preview collection of robotics applications, libraries, samples, and benchmarking tools to help you build solutions faster. It includes models and pipelines optimized with the OpenVINO™ toolkit for accelerated performance on Intel® CPUs, integrated GPUs, and NPUs. Refer to the [detailed user guide and documentation](https://docs.openedgeplatform.intel.com/dev/ai-suite-robotics.html).

The **Robotics AI Suite** is organized into **collections** that group workflows and capabilities for different robot categories. Each collection provides:

- Libraries for core robotics workloads and control recipes.
- Integration with ROS 2, supported sensor profiles, and benchmarking tools.
- OpenVINO™-optimised models for computer vision, large language models (LLMs), and vision-language-action (VLA).
- Hardware acceleration on Intel® CPUs, integrated GPUs, and NPUs for faster inference.

The types of collection are as follows:

- **Humanoid Imitation Learning**
  For robots that learn and replicate human actions to perform interactive or assistive tasks.
- **Autonomous Mobile Robots (AMRs)**
  For robots that navigate and operate independently in dynamic environments such as warehouses or factories.
- **Stationary Robot Vision & Control**
  For fixed-position robots using vision systems for tasks like inspection, assembly, or quality control.

## Architecture

The diagram below is the single, consolidated view of the Robotics AI Suite. It shows the major software components, how perception, navigation, manipulation, Physical AI, and benchmarking relate, which parts are Intel-provided versus upstream open source, and how workloads map onto Intel® heterogeneous compute (CPU / iGPU / NPU). You should be able to understand what the suite includes — and where Intel adds value — without reading further.

![Robotics AI Suite reference architecture](docs/images/architecture/Robotics-AI-Suite-Architecture.png)

**How to read it**

- Colour tells you ownership: **Intel-provided / optimized** (blue), **ROS 2 / upstream open source** (green), **Intel® silicon** (dark blue), and **user-supplied** robot, sensors, and datasets (grey). A **★** marks Intel value-add over the upstream component.
- The stack is layered top-to-bottom: **developer experience & tooling**, **AI models & pipelines** (OpenVINO™-optimized), **robotics middleware & frameworks** on **ROS 2**, **system software** (real-time kernel, drivers, EtherCAT), and the **Intel® Core™ / Core™ Ultra** hardware. Everything above the hardware line is what you consolidate onto a single Intel platform.

**What you get, and how it fits together**

- **Perception, navigation, and manipulation** are ROS 2 stacks. Intel adds optimized components on top of upstream Nav2, MoveIt, and ORB-SLAM3 — ITS-Planner, FastMapping, Collaborative SLAM, ADBScan, and GroundFloor Segmentation for AMRs; Robot Vision & Control (RVC) and Visual Servoing (CNS) for stationary arms.
- **Physical AI / Embodied models** — VLA (Pi0.5+RTC, RDT-1B), ACT, and Diffusion Policy / iDP3 — plus **LLM / VLM task planning** run through the OpenVINO™ runtime and oneAPI.
- **Benchmarking & tooling** — ROS 2 KPI monitoring, Gazebo simulation, sample applications, and model-optimization / setup tooling — sit in the top developer-experience layer.

**Where Intel accelerates the workload**

Perception and detection run on the **NPU / iGPU**; VLA / diffusion policies and LLM / VLM planning on the **iGPU** (optionally a discrete **Arc™ GPU**); deterministic motion control and planning on the **CPU** with a `PREEMPT_RT` kernel and EtherCAT. OpenVINO™ selects the device per workload, so perception, AI, planning, and real-time control are consolidated on one Intel® platform.

### Runtime data flow

Sensor data flows through perception into the AI decision models, then to planning and real-time control, and out to the actuators — with feedback closing the loop. Each stage is annotated with the compute it targets.

![Runtime data flow from sensors through models to control](docs/images/architecture/robotics-runtime-data-flow.png)

### Workloads mapped to Intel hardware

Each collection uses Intel heterogeneous compute differently. The matrix summarizes the primary (●) and optional (○) compute target for each collection.

![Collections mapped to Intel heterogeneous compute](docs/images/architecture/robotics-hardware-mapping.png)

The per-collection reference application architectures — which zoom into a representative end-to-end application — are shown on the collection pages linked in the tables below.

**Humanoid - Imitation Learning:**

| Application | Documentation | Description |
| ----------- | ------------- | ----------- |
| [Diffusion Policy (OpenVINO Toolkit)](pipelines/diffusion-policy-ov) | [Diffusion Policy (OpenVINO Toolkit)](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/sample_pipelines/diffusion_policy.html) | Diffusion Policy implementation optimized with OpenVINO toolkit |
| [Imitation Learning - ACT](pipelines/act-sample) | [Imitation Learning - ACT](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/sample_pipelines/imitation_learning_act.html) | Imitation learning pipeline using Action Chunking with Transformers(ACT) algorithm to train and evaluate in simulated or real robot environments with Intel® optimization |
| [Improved 3D Diffusion Policy (OpenVINO Toolkit)](pipelines/idp3-ov) | [Improved 3D Diffusion Policy (OpenVINO Toolkit)](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials/model_idp3.html) | Improved 3D Diffusion Policy implementation optimized with OpenVINO toolkit |
| [LLM Robotics Demo](pipelines/llm-robotics-demo) | [LLM Robotics Demo](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/sample_pipelines/llm_robotics.html) | Step-by-step guide for setting up a real-time system to control a JAKA robot arm with movement commands generated using an LLM |
| [Pi0.5 with Real-Time Chunking (OpenVINO Toolkit)](pipelines/pi05-rtc-ov) | [Pi0.5 with Real-Time Chunking (OpenVINO Toolkit)](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/sample_pipelines/pi05_with_rtc.html) | Implementation of Pi0.5 VLA model with Real-Time Chunking (RTC) optimized with the OpenVINO toolkit |
| [Robotics Diffusion Transformer (OpenVINO Toolkit)](pipelines/rdt-ov) | [Robotics Diffusion Transformer (OpenVINO Toolkit)](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/sample_pipelines/robotics_diffusion_transformer.html) | Robotics Diffusion Transformer implementation optimized with OpenVINO toolkit |
| [VSLAM: ORB-SLAM3](pipelines/orb-slam3-sample) | [VSLAM: ORB-SLAM3](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/sample_pipelines/ORB_VSLAM.html) | One of the popular real-time feature-based SLAM libraries that can perform Visual, Visual-Inertial and Multi-Map SLAM with monocular, stereo and RGB-D cameras, using pin-hole and fish-eye lens models |

**Autonomous Mobile Robot:**

| Algorithm | Documentation | Description |
| --------- | ------------- | ----------- |
| [ADBScan](components/adbscan) | [ADBScan](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/tutorials_amr/navigation/adbscan/index.html) | ADBSCAN (Adaptive DBSCAN) is an Intel-patented algorithm. It is a highly adaptive and scalable object detection and localization (clustering) algorithm, tested successfully to detect objects at all ranges for 2D Lidar, 3D Lidar, and RealSense™ depth camera. |
| [Collaborative-SLAM](components/collaborative-slam) | [Collaborative-SLAM](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/tutorials_amr/navigation/collaborative-slam.html) | A Collaborative Visual SLAM example that is compiled natively for both Intel® Core™ and Intel® Atom® processor-based systems. In addition, GPU acceleration may be enabled on selected Intel® Core™ processor-based system. |
| [Fastmapping](components/fast-mapping) | [Fastmapping](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/tutorials_amr/navigation/run-fastmapping-algorithm.html) | FastMapping application is the Intel® optimized version of octomap. |
| [GroundFloor Segmentation](components/groundfloor) | [GroundFloor Segmentation](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/tutorials_amr/perception/pointcloud-groundfloor-segmentation.html) | Showcases an Intel® algorithm designed for the segmentation of depth sensor data, compatible with 3D LiDAR or a RealSense™ camera inputs |
| [ITS-Planner](components/its-planner) | [ITS-Planner](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/tutorials_amr/navigation/its-path-planner-plugin.html) | Intelligent Sampling and Two-Way Search (ITS) global path planner is an Intel-patented algorithm. ITS is a new search approach based on two-way path planning and intelligent sampling, which reduces the compute time by about 20x-30x on a 1000-node map comparing with the A* search algorithm. |
| [Multi-Camera-Demo](components/multicam-demo) | [Multicam-Demo](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/tutorials_amr/perception/openvino/pyrealsense2_d457_multicam_object_detection_tutorial.html) | Demonstrates the multi-camera use case using an Axiomtek ROBOX500 ROS2 AMR controller and four RealSense™ depth cameras D457 |
| [Object Detection](components/object-detection) | [Object Detection](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/tutorials_amr/perception/openvino/object_detection_tutorial.html) | An example on using the ROS 2 node with OpenVINO toolkit. It outlines the steps for installing the node and executing the object detection model. |
| [Simulations](components/simulations) | [Simulations](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/tutorials_amr/simulation/index.html) | Tutorials on using the ROS 2 simulations with the Autonomous Mobile Robot. You can test robot sensing and navigation in these simulated environments. |
| [Wandering](components/wandering) | [Wandering](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/tutorials_amr/navigation/wandering_app/index.html) | Wandering mobile robot application is a ROS 2 sample application. It can be used with different SLAM algorithms in combination with the ROS2 navigation stack, to move the robot around in an unknown environment. The goal is to create a navigational map of the environment. |

**Stationary Robot Vision & Control:**

| Application | Documentation | Description |
| ----------- | ------------- | ----------- |
| [Stationary Robot Vision & Control](robot-vision-control) | [Stationary Robot Vision & Control](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/rvc/index.html) | Stationary Robot Vision & Control is a robotic software framework aimed at tackling pick-and-place and track-and-place industrial problems. This is under active development, hence released in the *pre-release* quality. |

**OpenVINO™ Toolkit-Optimized Model Algorithms:**

| Algorithm | Description |
| --------- | ----------- |
| [YOLOv8](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials.html#model-tutorials) | CNN-based object detection |
| [YOLOv12](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials.html#model-tutorials) | CNN-based object detection |
| [MobileNetV2](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials.html#model-tutorials) | CNN-based object detection |
| [SAM](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials.html#model-tutorials) | Transformer-based segmentation |
| [SAM2](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials.html#model-tutorials) | Extends SAM for video segmentation and object tracking with cross attention to memory |
| [FastSAM](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials.html#model-tutorials) | Lightweight substitute to SAM |
| [MobileSAM](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials.html#model-tutorials) | Lightweight substitute to SAM (Same model architecture with SAM. Refer to the OpenVINO toolkit and Segment Anything Model (SAM) tutorials for model exporting and application) |
| [U-NET](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials.html#model-tutorials) | CNN-based segmentation and diffusion model |
| [DETR](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials.html#model-tutorials) | Transformer-based object detection |
| [DETR GroundingDino](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials.html#model-tutorials) | Transformer-based object detection |
| [CLIP](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials.html#model-tutorials) | Transformer-based image classification |
| [Qwen2.5VL](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials.html#model-tutorials) | Multimodal large language model |
| [Whisper](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials.html#model-tutorials) | Automatic speech recognition |
| [FunASR](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials.html#model-tutorials) | Automatic speech recognition |
| [Action Chunking with Transformers - ACT](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials/model_act.html#model-act) | An end-to-end imitation learning model designed for fine manipulation tasks in robotics |
| [Visual Servoing - CNS](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials/model_cns.html) | A technique that uses feedback information extracted from a vision sensor to control robot motion |
| [Diffusion Policy](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials/model_dp.html) | The ability to learn the gradient of the action distribution score function and optimize through the stochastic Langevin dynamics steps during inference provides a stable and efficient way to find optimal actions |
| [Improved 3D Diffusion Policy (iDP3)](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials/model_idp3.html) | Improved 3D Diffusion Policy (iDP3) builds upon the original Diffusion Policy framework by enhancing its capabilities for 3D robotic manipulation tasks |
| [Robotics Diffusion Transformer (RDT-1B)](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials/model_rdt.html) | Robotics Diffusion Transformer with 1.2B parameters (RDT-1B), is a diffusion-based foundation model for robotic manipulation |
| [Feature Extraction Model: SuperPoint](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials/model_superpoint.html#model-superpoint) | A self-supervised framework for interest point detection and description in images, suitable for a large number of multiple-view geometry problems in computer vision |
| [Feature Tracking Model: LightGlue](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials/model_lightglue.html#model-lightglue) | A model designed for efficient and accurate feature matching in computer vision tasks |
| [Bird’s Eye View Perception: Fast-BEV](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials/model_fastbev.html#model-fastbev) | Obtaining a Bird's Eye View (BEV) perception is to gain a comprehensive understanding of the spatial layout and relationships between objects in a scene |
| [Monocular Depth Estimation: Depth Anything V2](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/embodied/model_tutorials/model_depthanythingv2.html#model-depthanythingv2) | A powerful tool that leverages deep learning to infer 3D information from 2D images |
