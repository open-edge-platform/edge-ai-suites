.. _model_lightglue:

Feature Tracking Model: LightGlue
#################################

LightGlue is a model designed for efficient and accurate feature matching in computer vision tasks. It builds upon the 
principles of feature matching, which is crucial for applications like image stitching, 3D reconstruction, and visual
localization. LightGlue aims to provide a lightweight and high-performance solution for these tasks.

LightGlue is designed to address the challenges of feature matching by providing a model that is both computationally
efficient and capable of producing high-quality matches. It leverages advancements in deep learning to improve the
robustness and accuracy of feature matching, while also being optimized for real-time performance.

.. image:: assets/images/lightglue.png
   :width: 85%
   :align: center


**Model Architecture:**

- Transformer Backbone:

  - Define a layer as a succession of one self-attention unit and one cross-attention unit.

- Correspondence Prediction:

  - Design a lightweight head that predicts an assignment given the updated state at any layer.

- Adaptive depth and width:

  - Reduce the number of layers depending on the difficulty of the input image pair.
  - Prune out points that are confidently rejected early.

- Supervised training in 2 stages:

  - First train it to predict correspondences and only after train the confidence classifier. 
  - The latter thus does not impact the accuracy at the final layer or the convergence of the training.

**More Information:**

- Full paper: https://arxiv.org/pdf/2306.13643
- Github link: https://github.com/cvg/LightGlue

Model Conversion
================
The LightGlue model is trained using |pytorch| but can achieve optimized inference performance on Intel devices using |OpenVINO|.
To enable this, the |pytorch| model must first be converted to the |OpenVINO| IR format. This process is done in two stages: first converting to ONNX, and then converting to IR format.

.. contents:: Table of Contents
   :local:

Export LightGlue to ONNX
-------------------------
Before converting the model to OpenVINO IR, it is best practice to first export the PyTorch model to ONNX format. The ONNX model format allows for interoperability across different platforms with support for multiple execution providers and removes Python-specific dependencies such as PyTorch.
The repository `LightGlue-ONNX <https://github.com/fabio-sim/LightGlue-ONNX>`_ provides a simple command-line tool, ``dynamo.py``, to easily export LightGlue to ONNX and perform inference using ONNX Runtime, based on `Typer <https://typer.tiangolo.com/>`_ to facilitate this conversion.

Exporting the model to ONNX
^^^^^^^^^^^^^^^^^^^^^^^^^^^
Prepare a python environment with the required dependencies by running the following command (python 3.11 or higher is required):

.. code-block:: bash

   $ pip install opencv-python==4.11.0.86 torch==2.6.0 typer==0.15.2 onnx==1.17.0 onnxruntime==1.21.0

Use the following command to export the LightGlue model to ONNX format:

.. code-block:: bash

   $ python dynamo.py export --output weights/superpoint_lightglue_pipeline_static.onnx --batch-size 2 --height 1280 --width 720

- ``--batch-size 2`` : Specifies the batch size for inference.
- ``--output weights/superpoint_lightglue_pipeline_static.onnx`` : Defines the output path for the ONNX model.
- ``--use-dynamo`` : Enables the use of ``torch.compile`` via Dynamo for optimized tracing.
- ``-h 1280 -w 720`` : Specifies the height and width of the input images.

Convert ONNX to OpenVINO IR
---------------------------
Ensure OpenVINO is Installed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^ 
.. note::  
   Make sure OpenVINO is installed by following the guide:  
   :ref:`Install OpenVINO via pip <openvino_install>` 

Once the model is in ONNX format, it can be converted to OpenVINO's Intermediate Representation (IR) format using OpenVINO’s command-line model conversion tool, ``ovc``.

Convert ONNX to OpenVINO IR using ovc
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The ``ovc`` tool simplifies the process of converting an ONNX model to OpenVINO IR format.

Run the following command to perform the conversion:

.. code-block:: bash

   $ ovc superpoint_lightglue_pipeline_static.onnx

By default, this command converts the ONNX model to FP16 IR format, generating the following files:

- ``superpoint_lightglue_pipeline_static.xml`` : Defines the model topology.
- ``superpoint_lightglue_pipeline_static.bin`` : Stores the model weights and binary data.

If you need an FP32 precision model, add the following parameter to the ovc conversion command:

.. code-block:: bash

   $ ovc superpoint_lightglue_pipeline_static.onnx --compress_to_fp16=False
