.. _model_tutorials:

Model Tutorials
################

Intel OpenVINO supports most of the TensorFlow and PyTorch models. The table below lists some deep learning models that commonly used in the Embodied Intelligence solutions. You can find information about how to run them on Intel platforms:

      .. list-table::
         :widths: 20 40 50
         :header-rows: 1

         * - Algorithm 
           - Description
           - Link
         * - YOLOv8
           - CNN based object detection
           - https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/yolov8-optimization
         * - YOLOv12
           - CNN based object detection
           - https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/yolov12-optimization
         * - MobileNetV2
           - CNN based object detection
           - https://github.com/openvinotoolkit/open_model_zoo/blob/master/models/public/mobilenet-v2-1.0-224
         * - SAM
           - Transformer based segmentation
           - https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/segment-anything
         * - SAM2
           - Extend SAM to video segmentation and object tracking with cross attention to memory
           - https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/sam2-image-segmentation
         * - FastSAM
           - Lightweight substitute to SAM
           - https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/fast-segment-anything
         * - MobileSAM
           - Lightweight substitute to SAM (Same model architecture with SAM. Can refer to OpenVINO SAM tutorials for model export and application)
           - https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/segment-anything
         * - U-NET
           - CNN based segmentation and diffusion model
           - https://community.intel.com/t5/Blogs/Products-and-Solutions/Healthcare/Optimizing-Brain-Tumor-Segmentation-BTS-U-Net-model-using-Intel/post/1399037?wapkw=U-Net
         * - DETR
           - Transformer based object detection
           - https://github.com/openvinotoolkit/open_model_zoo/tree/master/models/public/detr-resnet50
         * - GroundingDino
           - Transformer based object detection
           - https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/grounded-segment-anything
         * - CLIP
           - Transformer based image classification
           - https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/clip-zero-shot-image-classification

Please also find information for the models of imitation learning, grasp generation, simultaneous localization and mapping (SLAM) and bird's-eye view (BEV):

.. toctree::
    :maxdepth: 1

    model_tutorials/model_act
    model_tutorials/model_superpoint
    model_tutorials/model_lightglue
    model_tutorials/model_fastbev
    model_tutorials/model_depthanythingv2

    
