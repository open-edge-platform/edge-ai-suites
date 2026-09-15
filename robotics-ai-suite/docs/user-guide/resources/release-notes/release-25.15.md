# Release Notes: Robotics AI Suite 25.15

## Humanoid Toolkit 25.15

Humanoid Toolkit v25.15 provides necessary software framework, libraries, tools, BKC, tutorials and example codes to facilitate humanoid solution development on Intel® Core™ Ultra Series 2 processors (Arrow Lake-H), It provides Intel Linux LTS kernel v6.12.8 with Preempt-RT, and supports for Canonical Ubuntu OS 22.04, introduces initial support for ROS2 Humble software libraries and tools. It supports many models optimization with OpenVINO™ toolkit, and provides typical workflows and examples including ACT manipulation, ORB-SLAM3, etc.

**New**

- Provided Linux OS 6.12.8 BSP with Preempt-RT
- Provided Real-time optimization BKC
- Optimized IgH EtherCAT master with Linux kernel v6.12
- Added ACT manipulation pipeline with OpenVINO™ and Intel® Extension for PyTorch framework optimization
- Added ORB-SLAM3 pipeline focuses on real-time simultaneous localization and mapping
- Provided typical AI models optimization tutorials with OpenVINO™ toolkit
- Added pipelines:

  | Pipeline Name | Description |
  | --- | --- |
  | [Imitation Learning - ACT](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-suites/robotics-ai-suite/embodied/sample_pipelines/imitation_learning_act.html) | Imitation learning pipeline using Action Chunking with Transformers(ACT) algorithm to train and evaluate in simulator or real robot environment with Intel optimization |
  | [VSLAM: ORB-SLAM3](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-suites/robotics-ai-suite/embodied/sample_pipelines/ORB_VSLAM.html) | One of popular real-time feature-based SLAM libraries able to perform Visual, Visual-Inertial and Multi-Map SLAM with monocular, stereo and RGB-D cameras, using pin-hole and fisheye lens models |


**Improved**

The following model algorithms were optimized by OpenVINO™ toolkit:

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

**Known Issues**

- There is a known deadlock risk and limitation to use ``intel_gpu_top`` to read i915 perf event in Preempt-RT kernel, it will be fixed with next release.
