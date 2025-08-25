.. _model_fastbev:

Bird's Eye View Perception: Fast-BEV
####################################

Bird's eye view (BEV) perception refers to a perspective in which the scene or objects are viewed from directly above,
resembling the view one would have if they were looking down from the sky onto the scene.

The purpose of obtaining a BEV perception is to gain a comprehensive understanding of the spatial layout and relationships
between objects in a scene. This top-down perspective can be particularly useful in various applications, including object tracking
and detection, navigation and mapping, environmental monitoring, etc. Furthermore, it is instrumental in enhancing situational
awareness and decision-making.

By adopting deep learning process, BEV perception makes a crucial concept and the-state-of-art implementations in the fields
of autonomous driving, mobile robotics, and humanoid robotics. As examples, here is an overview of its key use cases in robotics areas:

- Mobile Robots

  - **Obstacle Avoidance**: For mobile robots, a BEV allows for effective obstacle detection and avoidance, ensuring smooth navigation in dynamic environments.
  - **Path Planning**: BEV aids in efficient path planning by providing a clear map of the environment, which is essential for tasks like delivery, exploration, and surveillance.
  - **Localization and Mapping**: BEV contributes to simultaneous localization and mapping (SLAM) by offering a consistent frame of reference, which is crucial for robots operating in unknown or changing environments.
  - **Multi-Robot Coordination**: In scenarios involving multiple robots, BEV can facilitate coordination by providing a shared view of the environment, helping robots to avoid collisions and work together efficiently.

- Humanoid Robots

  - **Spatial Awareness**: For humanoid robots, BEV enhances spatial awareness, allowing them to interact more naturally and safely with their surroundings and with humans.
  - **Complex Task Execution**: BEV can assist humanoid robots in performing complex tasks that require an understanding of the environment from a top-down perspective, such as organizing objects or navigating through cluttered spaces.
  - **Human-Robot Interaction**: By providing a comprehensive view of the environment, BEV can improve the robot's ability to interpret human gestures and actions, leading to more intuitive interactions.
  - **Balance and Stability**: For bipedal locomotion, BEV can help in maintaining balance and stability by providing real-time feedback on the robot's position relative to the ground and other objects.

In summary, Bird's Eye View is a powerful tool that enhances the capabilities of autonomous systems by providing
a comprehensive and intuitive understanding of the environment. This leads to improved safety, efficiency, and
interaction in various applications across autonomous driving, mobile robotics, and humanoid robotics.

Fast-BEV, as an representative of BEV algorithms, 

.. image:: assets/images/fastbev.png
   :width: 85%
   :align: center

**Model Architecture:**

- **Fast-Ray Transformation** with pre-computing the image-to-voxel index (Look-Up-Table) and letting all cameras project to the same dense voxel (Multi-View to One-Voxel) to speed up project.
- **Multi-Scale Image Encoder** with Multi-Scale Projection to obtain multi-scale features.
- **Efficient BEV Encoder** with efficient design to speed up inference time.
- **Data Augmentation** on image and BEV domain to avoid over-fitting and achieve better performance.
- **Temporal Fusion module** in BEV encoder stage to leverage multi-frame information.

**More Information:**

- Full paper: https://arxiv.org/pdf/2301.12511
- Github link: https://github.com/Sense-GVT/Fast-BEV

Model Conversion
================

The FastBEV model is trained using PyTorch but can achieve optimized inference performance on Intel devices using OpenVINO.  
To enable this, the PyTorch model must first be converted to the OpenVINO IR format.

All models (model.zip) can be downloaded from `Google Drive <https://drive.google.com/file/d/1wwwckM0vux5ub3U4R_zS9pm01QFmMPru/view>`_. The zip file contains the following:

- FastBEV ONNX models and PyTorch models.
- ResNet18 INT8 ONNX and PTQ models.

For additional details, refer to the official `CUDA-FastBEV GitHub repository`_.

.. contents:: Table of Contents
   :local:

ONNX Model Directory Structure
------------------------------

After unzipping `model.zip`, the following directory structure will be created:

::

    ├── resnet18
    │   ├── fastbev-det.pth
    │   ├── fastbev_post_trt_decode.onnx
    │   ├── fastbev_post_trt.onnx
    │   ├── fastbev_pre_trt.onnx
    ├── resnet18int8
    │   ├── fastbev_post_trt_decode.onnx
    │   ├── fastbev_pre_trt.onnx
    │   └── fastbev_ptq.pth
    └── resnet18int8head
        ├── bev_ptq_head.pth
        ├── fastbev_post_trt_decode.onnx
        └── fastbev_pre_trt.onnx

Convert ONNX to OpenVINO IR Using `ovc`
-------------------------------------------

Ensure OpenVINO is Installed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^  

.. note::  
   Make sure OpenVINO is installed by following the guide:  
   :ref:`Install OpenVINO via pip <openvino_install>` 

Once the model is in ONNX format, it can be converted to OpenVINO's Intermediate Representation (IR) format using OpenVINO's command-line model conversion tool, ``ovc``.

The ``ovc`` tool simplifies the process of converting an ONNX model to OpenVINO IR format.

Steps to Convert ONNX Models
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. **Navigate to the `resnet18` Folder**    
   
   Open a terminal and navigate to the folder containing the models:

   .. code-block::  bash
   
      $ cd resnet18

2. **Run the `ovc` Command for Each ONNX Model**  

   To convert `fastbev_post_trt_decode.onnx`:

   .. code-block::  bash
   
      $ ovc fastbev_post_trt_decode.onnx

   To convert `fastbev_post_trt.onnx`:

   .. code-block::  bash
   
      $ ovc fastbev_post_trt.onnx

   To convert `fastbev_pre_trt.onnx`:

   .. code-block::  bash
   
      $ ovc fastbev_pre_trt.onnx

By default, this command converts the ONNX model to FP16 IR format. The conversion will generate the following files for each model:

- ``<model_name>.xml`` : Defines the model topology.
- ``<model_name>.bin`` : Contains the model weights and binary data.

Expected Output
^^^^^^^^^^^^^^^^^^^^^^^^^^^^  

After running the ``ovc`` command, you should see the following output files for each model:

::

    fastbev_post_trt_decode.xml  
    fastbev_post_trt_decode.bin
    fastbev_post_trt.xml
    fastbev_post_trt.bin
    fastbev_pre_trt.xml
    fastbev_pre_trt.bin

You can now use these `.xml` and `.bin` files with OpenVINO for optimized inference on Intel hardware.

.. _CUDA-FastBEV GitHub repository: https://github.com/Mandylove1993/CUDA-FastBEV?tab=readme-ov-file
