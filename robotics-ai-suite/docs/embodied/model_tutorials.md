# Model Tutorials

The OpenVINO™ toolkit supports most TensorFlow and PyTorch models. The following table lists deep-learning models commonly used in the Embodied Intelligence solutions, and information on how to run them on Intel® platforms:

| Algorithm     | Description                                                                                                                         | Link                                                                                                                                                                                                         |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| YOLOv8        | CNN-based object detection                                                                                                          | [YOLOv8](https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/yolov8-optimization)                                                                                                    |
| YOLOv12       | CNN-based object detection                                                                                                          | [YOLOv12](https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/yolov12-optimization)                                                                                                  |
| MobileNetV2   | CNN-based object detection                                                                                                          | [MobileNetV2](https://github.com/openvinotoolkit/open_model_zoo/blob/master/models/public/mobilenet-v2-1.0-224)                                                                                              |
| SAM           | Transformer-based segmentation                                                                                                      | [SAM](https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/segment-anything)                                                                                                          |
| SAM2          | Extends SAM to video segmentation and object tracking with cross attention to memory                                                | [SAM2](https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/sam2-image-segmentation)                                                                                                  |
| FastSAM       | Lightweight substitute to SAM                                                                                                       | [FastSAM](https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/fast-segment-anything)                                                                                                 |
| MobileSAM     | Lightweight substitute to SAM (Same model architecture as SAM. See OpenVINO SAM tutorials for model export and application)         | [MobileSAM](https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/segment-anything)                                                                                                    |
| U-NET         | CNN-based segmentation and diffusion model                                                                                          | [U-NET](https://community.intel.com/t5/Blogs/Products-and-Solutions/Healthcare/Optimizing-Brain-Tumor-Segmentation-BTS-U-Net-model-using-Intel/post/1399037?wapkw=U-Net)                                     |
| DETR          | Transformer-based object detection                                                                                                  | [DETR](https://github.com/openvinotoolkit/open_model_zoo/tree/master/models/public/detr-resnet50)                                                                                                            |
| GroundingDino | Transformer-based object detection                                                                                                  | [GroundingDino](https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/grounded-segment-anything)                                                                                       |
| CLIP          | Transformer-based image classification                                                                                              | [CLIP](https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/clip-zero-shot-image-classification)                                                                                      |
| Qwen2.5VL     | Multimodal large language model                                                                                                     | [Qwen2.5VL](https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/qwen2.5-vl)                                                                                                          |
| Whisper       | Automatic speech recognition                                                                                                        | [Whisper](https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/whisper-asr-genai)                                                                                                     |
| FunASR        | Automatic speech recognition                                                                                                        | [FunASR Setup in LLM Robotics - sample pipeline](sample_pipelines/llm_robotics.md#set-up-the-fundamental-end-to-end-speech-recognition-funasr-toolkit)                                                       |

> **Attention:**
  When following these tutorials for model conversion, ensure that the OpenVINO toolkit version used for model conversion is the same as the runtime version used for inference. Otherwise, unexpected errors may occur, especially if the model is converted using a newer version and the runtime is an older version. See details in the [Troubleshooting](../troubleshooting.md#humanoid_embodied_troubleshooting) section.

Please also find information for the models of imitation learning, grasp generation, simultaneous localization and mapping (SLAM) and bird's-eye view (BEV):

<!--hide_directive:::{toctree}
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
:::hide_directive-->
