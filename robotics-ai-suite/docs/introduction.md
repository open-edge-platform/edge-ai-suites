# Introduction

The Robotics AI Suite is an open-source toolkit for developing robots that sense, interact, and make decisions at the edge. Built on a unified Intel platform, the Suite combines modular tools for vision, control, and AI inference, accelerating integration and deployment.

Whatever your robotics workload - if you are bringing up a new platform, integrating sensors and actuators, or optimizing an AI workload with Intel - these documents help you find compatible ingredients and pipelines for your robotics application and guidance for deploying on Intel hardware.

:::{image} images/intro-light.png
:class: only-light
:::

:::{image} images/intro-dark.png
:class: only-dark
:::

## Industry Segments

The Robotics AI Suite targets the following industry segments:

- **[Autonomous Mobile Robot](hardware_blueprints/amr/index.md)** — Wheeled or tracked robots that navigate dynamic environments without fixed guidance, using onboard sensing, mapping, and path planning. Common in warehouse logistics, material transport, inspection, and last-mile delivery.

- **[Humanoid](hardware_blueprints/humanoid/index.md)** — Human-shaped robots with articulated limbs designed to operate in spaces and with tools built for people. Used for manipulation, locomotion, and interactive tasks in service, research, and general-purpose automation.

- **[Stationary Arm](hardware_blueprints/stationary_arm/index.md)** — Fixed-base robotic manipulators that perform precise, repeatable operations within a defined workspace. Typical applications include pick-and-place, assembly, welding, and machine tending on production lines.

## Reference Applications and Ingredients

The table below lists the reference applications, sample pipelines, and tutorials available across this documentation. The **Domains** column categorizes each entry to help you find relevant material for your application.

| Reference | Domains | Description |
|---|---|---|
| [RealSense Camera with ROS 2 Sample Application](components/sensors/reference_applications/realsense-ros2.md) | Sensors, Middleware | Integrates an RealSense camera with ROS 2 to stream color and depth data, launch camera nodes, and visualize the feed in RViz2. |
| [3D Pointcloud Groundfloor Segmentation for RealSense Camera and 3D LiDAR](components/sensors/reference_applications/pointcloud-groundfloor-segmentation.md) | Sensors, AI | Intel algorithm that classifies 3D point clouds from RealSense or LiDAR sensors into ground, elevated surfaces, and obstacles for navigation over challenging terrain. |
| [Multi-Camera Object Detection Powered by OpenVINO™](components/ai_resources/openvino/reference_applications/openvino_multicam_demo.md) | AI, OpenVINO, Sensors | Runs OpenVINO™-optimized YOLOv8 object detection and segmentation in parallel across up to four USB or GMSL cameras. |
| [OpenVINO™ Object Detection Tutorial](components/ai_resources/openvino/reference_applications/object_detection_tutorial.md) | AI, OpenVINO, Sensors, Middleware | Deploys a ROS 2 OpenVINO™ node for object detection with selectable CPU, GPU, or NPU inference devices. |
| [OpenVINO™ Yolov8 Tutorial](components/ai_resources/openvino/reference_applications/yolov8_openvino_tutorial.md) | AI, OpenVINO, Sensors, Middleware | Installs a ROS 2 OpenVINO™ node and runs a YOLOv8 segmentation model on the CPU using a RealSense camera image as input. |
| [OpenVINO™ Tutorial with Segmentation](components/ai_resources/openvino/reference_applications/segmentation_realsense_tutorial.md) | AI, OpenVINO, Sensors, Middleware | Runs a ROS 2 OpenVINO™ semantic segmentation model on CPU or GPU using a RealSense camera image as input. |
| [Collaborative Visual SLAM](components/optimized_solutions/collaborative-slam.md) | Autonomous Mobile Robot, SLAM | Multi-robot visual SLAM optimized with SSE/AVX2 instruction sets for map building and merging on Intel® CPUs and GPUs. |
| [FastMapping Algorithm](components/optimized_solutions/run-fastmapping-algorithm.md) | Autonomous Mobile Robot, Sensors | Intel-optimized octomap implementation that builds 3D voxel maps from RealSense depth camera data for efficient environment representation. |
| [ADBSCAN Follow-me](components/optimized_solutions/adbscan-follow-me.md) | Autonomous Mobile Robot, AI, Sensors | Adaptive DBSCAN person detection and tracking from 2D/3D LiDAR or RealSense point clouds, with Gazebo simulation and real-robot deployment examples. |
| [ITS Path Planner ROS 2 Navigation Plugin](components/optimized_solutions/its-path-planner-plugin.md) | Autonomous Mobile Robot, Navigation | Intel patented global path planner delivering 20-30x speedup over A* for the ROS 2 Navigation2 stack. |
| [Robot Re-localization Package for ROS 2 Navigation](components/optimized_solutions/navigation-relocalization.md) | Autonomous Mobile Robot, Navigation | Re-localization algorithm that rapidly recovers robot pose in Nav2 after sensor glitches or environment disturbances. |
| [GPU ORB Extractor](components/optimized_solutions/orb-extractor.md) | Autonomous Mobile Robot, SLAM | GPU-accelerated keypoint and descriptor extraction for Visual SLAM front-ends, with OpenCV and OpenCV-free APIs. |
| [Deploy Robot Teleop Using a Keyboard](software_references/amr/deployment/teleop_deploy.md) | Autonomous Mobile Robot | Validates motor control on a deployed robot using keyboard teleoperation before running autonomous workloads. |
| [Deploying `wandering`](software_references/amr/deployment/wandering_deploy.md) | Autonomous Mobile Robot, Navigation | Deploys the Wandering autonomous exploration pipeline on a physical robot using RTAB-Map and Nav2. |
| [Simulated Robotics with Gazebo](software_references/amr/simulation/basic_sim.md) | Autonomous Mobile Robot, Simulation | Introduces simulating robots as digital twins in Gazebo to test robotics applications before real-world deployment. |
| [Simulating `wandering` in Gazebo](software_references/amr/simulation/wandering_sim.md) | Autonomous Mobile Robot, Simulation, Navigation | Simulates the full Wandering pipeline in Gazebo with mapping, frontier exploration, and Nav2-based navigation. |
| [Gazebo Pick & Place Demo](components/middleware/gazebo/reference_applications/picknplace.md) | Middleware, Manipulation, Simulation | Coordinates two UR5 arms and a TurtleBot3 AMR on a conveyor line using MoveIt2 and Nav2 in Gazebo Classic. |
| [Imitation Learning - ACT](software_references/humanoid/sample_pipelines/imitation_learning_act.md) | Humanoid, AI, OpenVINO, Manipulation | Imitation learning pipeline using Action Chunking with Transformers, optimized with OpenVINO™, for fine manipulation in simulation and on real ALOHA robots. |
| [Model Predictive Control Demo](software_references/humanoid/sample_pipelines/mpc_demo.md) | Humanoid, AI, Manipulation | Combines ACT imitation learning with OCS2 model predictive control and MuJoCo simulation for perception-action manipulation control. |
| [Diffusion Policy](software_references/humanoid/sample_pipelines/diffusion_policy.md) | Humanoid, AI, OpenVINO, Manipulation | Visuomotor diffusion-policy pipeline for the Push-T manipulation task, with Transformer- and CNN-based variants optimized by OpenVINO™. |
| [VSLAM: ORB-SLAM3](software_references/humanoid/sample_pipelines/ORB_VSLAM.md) | Humanoid, SLAM | Real-time feature-based Visual SLAM supporting monocular, stereo, and RGB-D cameras, with EUROC dataset and RealSense demos. |
| [LLM Robotics Demo](software_references/humanoid/sample_pipelines/llm_robotics.md) | Humanoid, AI, Manipulation | Code-generation pipeline combining an LLM (Phi-4), vision models (SAM, CLIP), and a JAKA arm for voice- or text-commanded robot control. |
| [Robotics Diffusion Transformer (RDT)](software_references/humanoid/sample_pipelines/robotics_diffusion_transformer.md) | Humanoid, AI, OpenVINO, Manipulation | Bimanual manipulation foundation model with a unified action space, running in MuJoCo simulation and on real ALOHA robots with OpenVINO™ optimization. |
| [Pi0.5 with Real-Time Chunking](software_references/humanoid/sample_pipelines/pi05_with_rtc.md) | Humanoid, AI, OpenVINO, Manipulation | Vision-Language-Action pipeline pairing a PaliGemma VLM with a flow-matching policy and real-time chunking for smooth high-frequency control, accelerated with OpenVINO™. |
| [Action Chunking with Transformers - ACT](components/ai_resources/openvino/models/model_act.md) | AI, OpenVINO, Manipulation | Imitation learning model that predicts action chunks with Transformers for fine manipulation, including conversion to OpenVINO™ IR. |
| [Diffusion Policy (Model)](components/ai_resources/openvino/models/model_dp.md) | AI, OpenVINO, Manipulation | Visuomotor policy using conditional denoising diffusion to handle multimodal action distributions, with low-dim and image variants and OpenVINO™ conversion. |
| [Robotics Diffusion Transformer (RDT-1B)](components/ai_resources/openvino/models/model_rdt.md) | AI, OpenVINO, Manipulation | 1.2B-parameter diffusion foundation model for manipulation pre-trained on 46 datasets, with OpenVINO™ IR conversion guidance. |
| [General-purpose robot foundation model (Pi0)](components/ai_resources/openvino/models/model_pi0.md) | AI, OpenVINO, Manipulation | Vision-Language-Action foundation model pairing a PaliGemma VLM with an action-expert diffusion transformer, including OpenVINO™ conversion. |
| [BC-RNN & BC-Transformer](components/ai_resources/openvino/models/model_bc_rnn.md) | AI, OpenVINO, Manipulation | Behavior cloning models using RNN or Transformer backbones to map observations to actions from expert demonstrations. |
| [Visual Servoing - CNS](components/ai_resources/openvino/models/model_cns.md) | AI, OpenVINO, Manipulation | Graph neural network image-based visual servo policy achieving sub-millimeter precision at real-time (~40 fps) rates. |
| [GraspNet - Baseline](components/ai_resources/openvino/models/model_graspnet.md) | AI, OpenVINO, Manipulation | Grasp generation model trained on GraspNet-1Billion that predicts scored 6-DoF grasp poses from point clouds. |
| [Feature Extraction Model: SuperPoint](components/ai_resources/openvino/models/model_superpoint.md) | AI, OpenVINO, SLAM | Self-supervised interest point detector and descriptor generator with homographic adaptation for cross-domain generalization. |
| [Feature Tracking Model: LightGlue](components/ai_resources/openvino/models/model_lightglue.md) | AI, OpenVINO, SLAM | Lightweight transformer feature matcher with adaptive depth and width for efficient correspondence in 3D reconstruction and localization. |
| [Improved 3D Diffusion Policy (iDP3)](components/ai_resources/openvino/models/model_idp3.md) | AI, OpenVINO, Manipulation | Enhanced 3D manipulation policy that encodes point clouds with a 3D visual encoder and generates actions via diffusion. |
| [Bird's Eye View Perception: Fast-BEV](components/ai_resources/openvino/models/model_fastbev.md) | AI, OpenVINO, Navigation | Efficient multi-scale bird's-eye-view perception model for obstacle avoidance, path planning, and spatial awareness. |
| [Monocular Depth Estimation: Depth Anything V2](components/ai_resources/openvino/models/model_depthanythingv2.md) | AI, OpenVINO, Sensors | Monocular depth estimation foundation model (25M-1.3B parameters) for cost-effective depth perception without LiDAR. |
| [Wandering AMR Pipeline Benchmark](components/benchmarking/robotics-system-profiler/wandering-benchmark.md) | Benchmarking, Autonomous Mobile Robot | Automated benchmarking of the Wandering AMR pipeline, measuring latency, resource usage, and optional GPU/NPU KPIs across runs. |
| [Pick & Place Pipeline Benchmark](components/benchmarking/robotics-system-profiler/picknplace-benchmark.md) | Benchmarking, Manipulation | Automated benchmarking of the multi-robot Pick & Place simulation, capturing lifecycle metrics and aggregated KPIs. |


## Next Steps

Continue to the System Requirements guide to learn about supported Intel processors, OS requirements, and development kits:

- **[System Requirements](platform_foundation/system_requirements.md)** — select a platform and install an OS distribution.


:::{toctree}
:caption: Platform Foundation
:hidden:

System Requirements <platform_foundation/system_requirements.md>
Getting Started <platform_foundation/getting_started.md>
:::

:::{toctree}
:caption: Components
:hidden:


Intel Optimized Robotics Solutions and Ingredients <components/optimized_solutions/index>
Real-time Determinism <components/realtime_determinism/index>
Benchmarking <components/benchmarking/index>
Security <components/security/index>
Middleware <components/middleware/index>
Sensors <components/sensors/index>
AI Resources <components/ai_resources/index>
:::

:::{toctree}
:caption: Hardware Blueprints
:hidden:

Autonomous Mobile Robot <hardware_blueprints/amr/index>
Humanoid Robot <hardware_blueprints/humanoid/index>
Stationary Arm <hardware_blueprints/stationary_arm/index>
:::

:::{toctree}
:caption: Software References
:hidden:

Autonomous Mobile Robot <software_references/amr/index>
Humanoid Robot <software_references/humanoid/index>
Stationary Arm<software_references/stationary_arm/index>
:::

:::{toctree}
:caption: Resources
:hidden:

Migrating from NVIDIA <resources/migrating_from_nvidia/index>
Heterogeneous Computing <resources/heterogeneous_computing.md>
Release Notes <resources/release-notes.md>
Troubleshooting <resources/troubleshooting.md>
Glossary <resources/glossary.md>
:::