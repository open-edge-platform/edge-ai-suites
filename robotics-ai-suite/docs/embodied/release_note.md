# Release Notes

Click each tab to learn about the new and updated features in each release of Embodied Intelligence SDK.

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> Embodied Intelligence SDK v25.36
<!--hide_directive:sync: tab1hide_directive-->

Embodied Intelligence SDK v25.36 enhances model optimization capabilities with OpenVINO™ toolkit and provides typical workflows and examples, including Diffusion Policy (DP), Robotic Diffusion Transformer (RDT), Improved 3D Diffusion Policy (IDP3), Visual Servoing (CNS) and LLM Robotic Demo. This release has also updated the real-time optimized best-known configuration (BKC) on improving AI and control performance, and supporting the Intel® Arc™ B-series graphics card (B570).

**New Features:**

* Updated real-time optimization BKC, including BIOS and runtime optimization, balancing performance with AI and control consolidation.
* Added support for Intel® Arc™ B-series (Battlemage) graphics card (B570).
* Fixed deadlock issue when reading i915 perf event in Preempt-RT kernel.
* New EtherCAT Master stack features supporting user-space EtherCAT Master and multiple EtherCAT masters.
* Added Diffusion Policy pipeline with OpenVINO™ toolkit optimization.
* Added Robotics Diffusion Transformer (RDT) pipeline with OpenVINO toolkit optimization.
* Added Improved 3D Diffusion Policy (IDP3) model with OpenVINO toolkit optimization.
* Added Visual Servoing (CNS) model with OpenVINO toolkit optimization.
* Provided new tutorials for typical AI model optimization with OpenVINO toolkit.
* ACRN hypervisor's initial enablement on Arrow Lake platform.
* Added new Dockerfile to build containerized Robotics Development Toolkit (RDT) pipeline.

**Known Issues and Limitations**

* ACRN hypervisor feature and performance

   #. iGPU performance degradation observed when using passthrough iGPU to VM on ACRN hypervisor.

   #. Display becomes unresponsive in VMs when running concurrent AI workloads with iGPU SR-IOV enabled on ACRN hypervisor.

**The following model algorithms were added and optimized by OpenVINO™ toolkit:**

| Algorithm                                                | Description                                                                                                                                                   |
|----------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Qwen2.5VL                                                | Qwen2.5VL ****model_tutorials****                                                                                                                             |
| Whisper                                                  | Whisper ****model_tutorials****                                                                                                                               |
| FunASR (Automatic speech recognition)                    | Refer to the FunASR Setup ****funasr-setup**** in LLM Robotics sample pipeline                                                                                |
| Visual Servoing - CNS ****model_cns****                  | A graph neural network-based solution for image servo utilizing explicit keypoints correspondence obtained from any detector-based feature matching methods   |
| Diffusion Policy ****model_dp****                        | A visuomotor policy learning model in the field of robotic visuomotor policy learning, which represents policies as conditional denoising diffusion processes |
| Improved 3D Diffusion Policy (iDP3) ****model_idp3****   | A diffusion policy model enhancing capabilities for 3D robotic manipulation tasks                                                                             |
| Robotic Diffusion Transformer (RDT-1B) ****model_rdt**** | A diffusion-based foundation model for robotic manipulation                                                                                                   |

**The following pipelines were added:**

| Pipeline Name                                                               | Description                                                                                                                                                     |
|-----------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Diffusion Policy ****diffusion_policy****                                   | An innovative method for generating robot actions by conceptualizing visuomotor policy learning as a conditional denoising diffusion process                    |
| Robotics Diffusion Transformer (RDT) ****robotics_diffusion_transformer**** | A RDT pipeline provided for evaluating the VLA model on the simulation task                                                                                     |
| LLM Robotics Demo ****llm_robotics_demo****                                 | A code generation demo for robotics, interacting with a chatbot utilizing AI technologies such as large language models (Phi-4) and computer vision (SAM, CLIP) |


<!--hide_directive:::
:::{tab-item}hide_directive--> Embodied Intelligence SDK v25.15
<!--hide_directive:sync: tab2hide_directive-->

Embodied Intelligence SDK v25.15 provides necessary software framework, libraries, tools, BKC, tutorials and example codes to facilitate embodied intelligence solution development on Intel® Core™ Ultra Series 2 processors (Arrow Lake-H), It provides Intel Linux LTS kernel v6.12.8 with Preempt-RT, and supports for Canonical Ubuntu OS 22.04, introduces initial support for ROS2 Humble software libraries and tools. It supports many models optimization with OpenVINO™ toolkit, and provides typical workflows and examples including ACT manipulation, ORB-SLAM3, etc.

**New Features:**

* Provided Linux OS 6.12.8 BSP with Preempt-RT
* Provided Real-time optimization BKC
* Optimized IgH EtherCAT master with Linux kernel v6.12
* Added ACT manipulation pipeline with OpenVINO™ and Intel® Extension for PyTorch framework optimization
* Added ORB-SLAM3 pipeline focuses on real-time simultaneous localization and mapping
* Provided typical AI models optimization tutorials with OpenVINO™ toolkit

**Known Issues and Limitations**

* There is a known deadlock risk and limitation to use ``intel_gpu_top`` to read i915 perf event in Preempt-RT kernel, it will be fixed with next release.

**The following model algorithms were optimized by OpenVINO™ toolkit:**

| Algorithm                                                                   | Description                                                                                                                                                           |
|-----------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| YOLOv8 ****model_tutorials****                                              | CNN-based object detection                                                                                                                                            |
| YOLOv12 ****model_tutorials****                                             | CNN-based object detection                                                                                                                                            |
| MobileNetV2 ****model_tutorials****                                         | CNN-based object detection                                                                                                                                            |
| SAM ****model_tutorials****                                                 | Transformer-based segmentation                                                                                                                                        |
| SAM2 ****model_tutorials****                                                | Extend SAM to video segmentation and object tracking with cross attention to memory                                                                                   |
| FastSAM ****model_tutorials****                                             | Lightweight substitute to SAM                                                                                                                                         |
| MobileSAM ****model_tutorials****                                           | Lightweight substitute to SAM (Same model architecture with SAM. See OpenVINO toolkit's SAM tutorials for model export and application)                               |
| U-NET ****model_tutorials****                                               | CNN-based segmentation and diffusion model                                                                                                                            |
| DETR ****model_tutorials****                                                | Transformer-based object detection                                                                                                                                    |
| DETR GroundingDino ****model_tutorials****                                  | Transformer-based object detection                                                                                                                                    |
| CLIP ****model_tutorials****                                                | Transformer-based image classification                                                                                                                                |
| Action Chunking with Transformers - ACT ****model_act****                   | An end-to-end imitation learning model designed for fine manipulation tasks in robotics                                                                               |
| Feature Extraction Model: SuperPoint ****model_superpoint****               | A self-supervised framework for interest point detection and description in images, suitable for a large number of multiple-view geometry problems in computer vision |
| Feature Tracking Model: LightGlue ****model_lightglue****                   | A model designed for efficient and accurate feature matching in computer vision tasks                                                                                 |
| Bird's Eye View Perception: Fast-BEV ****model_fastbev****                  | Obtaining a BEV perception is to gain a comprehensive understanding of the spatial layout and relationships between objects in a scene                                |
| Monocular Depth Estimation: Depth Anything V2 ****model_depthanythingv2**** | A powerful tool that leverages deep learning to infer 3D information from 2D images                                                                                   |

**The following pipelines were added:**

| Pipeline Name                                                               | Description                                                                                                                                                     |
|-----------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Diffusion Policy ****diffusion_policy****                                   | An innovative method for generating robot actions by conceptualizing visuomotor policy learning as a conditional denoising diffusion process                    |
| Robotics Diffusion Transformer (RDT) ****robotics_diffusion_transformer**** | A RDT pipeline provided for evaluating the VLA model on the simulation task                                                                                     |
| LLM Robotics Demo ****llm_robotics_demo****                                 | A code generation demo for robotics, interacting with a chatbot utilizing AI technologies such as large language models (Phi-4) and computer vision (SAM, CLIP) |

<!--hide_directive:::
::::hide_directive-->
