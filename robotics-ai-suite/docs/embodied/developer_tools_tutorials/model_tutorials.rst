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
         * - Qwen2.5VL
           - Multimodal large language model
           - https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/qwen2.5-vl
         * - Whisper
           - Automatic speech recognition
           - https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/whisper-asr-genai
         * - FunASR
           - Automatic speech recognition
           - Refer to the :ref:`FunASR Setup <funasr-setup>` in LLM Robotics sample pipeline


.. attention::
   When following these tutorials for model conversion, please ensure that the OpenVINO version used for model conversion is the same as the runtime version used for inference. Otherwise, unexpected errors may occur, especially if the model is converted using a newer version and the runtime is an older version. See more details in the :ref:`Troubleshooting <ov_inference_troubleshooting>`.
   
Please also find information for the models of imitation learning, grasp generation, simultaneous localization and mapping (SLAM) and bird's-eye view (BEV):

.. note::
  Before using these models, please ensure that you have read the :ref:`AI Content Disclaimer <ai_content_disclaimer>`.

.. toctree::
    :maxdepth: 1

    model_tutorials/model_act
    model_tutorials/model_cns
    model_tutorials/model_dp
    model_tutorials/model_idp3
    model_tutorials/model_superpoint
    model_tutorials/model_lightglue
    model_tutorials/model_fastbev
    model_tutorials/model_depthanythingv2
    model_tutorials/model_rdt
   
 
