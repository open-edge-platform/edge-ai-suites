Release Notes
#############

Click each tab to learn about the new and updated features in each release of Intel® Embodied Intelligence SDK.

.. tabs::

   .. group-tab:: Embodied Intelligence SDK v25.14

      Embodied Intelligence SDK v25.14 provides necessary software framework, libraries, tools, BKC, tutorials and example codes to facilitate embodied intelligence solution development on |Intel| Core Ultra Series 2 processors (Arrow Lake-H), It provides Intel's |Linux| LTS kernel v6.12.8 with Preempt-RT, and supports for |Ubuntu| 22.04, introduces initial support for ROS2 Humble. It supports many models optimization with |OpenVINO|, and provides typical workflows and examples including ACT manipulation, ORB-SLAM3, etc.

      **New Features:**
      
      * Provided |Linux| OS 6.12.8 BSP with Preempt-RT
      * Provided Real-time optimization BKC
      * Optimized IgH EtherCAT master with |Linux| kernel v6.12
      * Added ACT manipulation pipeline with |OpenVINO|/|IPEX| optimization
      * Added ORB-SLAM3 pipeline focuses on real-time simultaneous localization and mapping
      * Provided typical AI models optimization tutorials with |OpenVINO|

      **The following model algorithms were optimized by Intel® OpenVINO™:**

      .. list-table::
         :widths: 20 80
         :header-rows: 1

         * - Algorithm 
           - Description
         * - :ref:`YOLOv8 <model_tutorials>`
           - CNN based object detection
         * - :ref:`YOLOv12 <model_tutorials>`
           - CNN based object detection
         * - :ref:`MobileNetV2 <model_tutorials>`
           - CNN based object detection
         * - :ref:`SAM <model_tutorials>`
           - Transformer based segmentation
         * - :ref:`SAM2 <model_tutorials>`
           - Extend SAM to video segmentation and object tracking with cross attention to memory
         * - :ref:`FastSAM <model_tutorials>`
           - Lightweight substitute to SAM
         * - :ref:`MobileSAM <model_tutorials>`
           - Lightweight substitute to SAM (Same model architecture with SAM. Can refer to OpenVINO SAM tutorials for model export and application)
         * - :ref:`U-NET <model_tutorials>`
           - CNN based segmentation and diffusion model
         * - :ref:`DETR <model_tutorials>`
           - Transformer based object detection
         * - :ref:`DETR GroundingDino <model_tutorials>`
           - Transformer based object detection
         * - :ref:`CLIP <model_tutorials>`
           - Transformer based image classification
         * - :ref:`Action Chunking with Transformers - ACT <model_act>`
           - An end-to-end imitation learning model designed for fine manipulation tasks in robotics
         * - :ref:`Feature Extraction Model: SuperPoint <model_superpoint>`
           - A self-supervised framework for interest point detection and description in images, suitable for a large number of multiple-view geometry problems in computer vision
         * - :ref:`Feature Tracking Model: LightGlue <model_lightglue>`
           - A model designed for efficient and accurate feature matching in computer vision tasks
         * - :ref:`Bird's Eye View Perception: Fast-BEV <model_fastbev>`
           - Obtaining a BEV perception is to gain a comprehensive understanding of the spatial layout and relationships between objects in a scene
         * - :ref:`Monocular Depth Estimation: Depth Anything V2 <model_depthanythingv2>`
           - A powerful tool that leverages deep learning to infer 3D information from 2D images

      **The following pipelines were added:**

      .. list-table::
         :widths: 20 80
         :header-rows: 1

         * - Pipeline Name 
           - Description
         * - :ref:`Imitation Learning - ACT <imitation_act>`
           - Imitation learning pipeline using Action Chunking with Transformers(ACT) algorithm to train and evaluate in simulator or real robot environment with Intel optimization
         * - :ref:`VSLAM: ORB-SLAM3 <orb_slam3>`
           - One of popular real-time feature-based SLAM libraries able to perform Visual, Visual-Inertial and Multi-Map SLAM with monocular, stereo and RGB-D cameras, using pin-hole and fisheye lens models
 

