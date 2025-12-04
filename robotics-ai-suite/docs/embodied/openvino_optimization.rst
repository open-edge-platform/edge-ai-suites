.. _pi05_lerobot_openvino:

OpenVINO™ Optimization of Robotics VLA Model Pi0.5
##################################################

This example shows how to optimize the Vision-Language-Action (VLA) model Pi0.5 with Intel® OpenVINO™, compress model weights to INT8 and benchmark using the OpenVINO benchmark_app tool.

What Steps VLA Models Perform
=============================

- **Vision**: Process and understand visual (image/video) information
- **Language**: Receive a language task (e.g., pick up the dishes)
- **Action**: Given the visual input (e.g., picture of the room) and natural language task (e.g., clean the room) and turn them into an action for the robot to take

About Pi0.5
===========

Pi0.5 is a state-of-the-art VLA model which supports long horizon tasks and open world generalization. During runtime when given a high level prompt (e.g., clean the room), Pi0.5 predicts relevant semantic subtasks giving the relevant behavior to perform next based on the semantics of the room layout (e.g., rearrange the pillow). Based on this subtask, the model then generates a low-level robot action chunk.


Overview
========

This tutorial covers:

- Converting the Pi0.5 model from PyTorch to ONNX
- Exporting the ONNX model to OpenVINO intermediate representation
- Compressing model weights to INT8 using NNCF
- Benchmarking the model using the OpenVINO benchmark tool
- Validating the optimized model outputs

Source Code
===========

The source code for this sample can be found here: `VLA-Pi0.5-OpenVINO <https://github.com/open-edge-platform/edge-ai-suites/tree/main/robotics-ai-suite/pipelines/vla-pi0.5-openvino>`_

Environment and Model Setup
===========================

#. Create a Python 3.10 virtual environment and activate it with the following command:

   .. code-block:: bash

      sudo apt install python3-venv
      python3 -m venv pi05_env
      source pi05_env/bin/activate

#. Install LeRobot from source with the following command:

   .. code-block:: bash

      git clone https://github.com/huggingface/lerobot.git
      cd lerobot
      pip install -e ".[pi]"

#. Install additional dependencies including OpenVINO and NNCF:

   .. code-block:: bash

      pip install onnx==1.20.0 openvino==2025.4.0 nncf==2.19.0

#. Within the LeRobot Pi0.5 source code, there are some operations which are not supported by ONNX and must be modified to ensure successful model conversion.

   Navigate to the ``modeling_pi05.py`` file found at ``lerobot/src/lerobot/policies/pi05/modeling_pi05.py`` and find the ``sample_noise()`` method as shown below.  This method samples from a normal distribution which will cause the ONNX conversion to fail.

   .. code-block:: python

      def sample_noise(self, shape, device):
          return torch.normal(
              mean=0.0,
              std=1.0,
              size=shape,
              dtype=torch.float32,
              device=device,
          )

   Now, modify this method set generated noise vector to instead initialize noise vector as zeros as shown below:

   .. code-block:: python

      def sample_noise(self, shape, device):
          return torch.zeros(shape, dtype=torch.float32, device=device)

   Additionally, within the ``modeling_pi05.py`` file, locate the ``sample_time()`` method. This samples from a beta distrubtion which will also cause ONNX export to fail.

   .. code-block:: python

      def sample_time(self, bsize, device):
          time_beta = sample_beta(
              self.config.time_sampling_beta_alpha, self.config.time_sampling_beta_beta, bsize, device
          )
          time = time_beta * self.config.time_sampling_scale + self.config.time_sampling_offset
          return time.to(dtype=torch.float32, device=device)

   Now Modify this ``sample_time()`` method to match that shown below. This sets the tensor value to the mean value for the mean of the beta distribution and will allow for successful model conversion:

   .. code-block:: python

      def sample_time(self, bsize, device):
          time = torch.full((bsize,), 1.5 / (1.5 + 1.0), device=device, dtype=torch.float32)  # Beta mean
          time = time * 0.999 + 0.001
          return time.to(dtype=torch.float32, device=device)

.. _pi05_model_conversion:

Model Conversion and OpenVINO™ Optimization
===========================================

#. Clone the edge-ai-suites repository and then run the :file:`convert_pytorch_onnx.py` script. This will download the HuggingFace Pi0.5 model taken from `here <https://huggingface.co/lerobot/pi05_base>`_ and will convert it to ONNX using the ``torch.onnx.export`` method.

   .. code-block:: bash

      cd ..
      git clone https://github.com/open-edge-platform/edge-ai-suites -b release-2025.2.0
      cd edge-ai-suites/robotics-ai-suite/pipelines/vla-pi0.5-openvino
      python convert_pytorch_onnx.py

#. Next, run the :file:`onnx_to_ov_ir.py` script. This will then generate the OV IR form of the model.

   .. code-block:: bash

      python onnx_to_ov_ir.py

   The snippet below shows how in this script the ONNX representation of the model is converted to OpenVINO using the ``openvino.convert_model`` method:

   .. code-block:: python

      ov_model = ov.convert_model("pi05_onnx/pi05.onnx")

#. Optionally, to compress the model to FP16 modify the ``openvino.save_model`` method in the :file:`onnx_to_ov_ir.py` by setting ``compress_to_fp16=True``:

   .. code-block:: python

      ov.save_model(ov_model,
                  output_model=f"{output_dir}/model.xml",
                  compress_to_fp16=True)

#. Run the :file:`nncf_int8_compression.py` file to quantize the OpenVINO Pi0.5 model to INT8.

   The snippet below shows how the uncompressed OpenVINO model is compressed to INT8 using Intel Neural Network Compression (NNCF):

   .. code-block:: python

      from nncf import compress_weights
      compression_mode = CompressWeightsMode.INT8_ASYM
      uncompressed_model = core.read_model(model=model_xml_path)
      compressed_model = compress_weights(
          model=uncompressed_model,
          mode=compression_mode,
          all_layers=True
      )

Benchmarking
============

To benchmark the model using the OpenVINO ``benchmark_tool`` application on CPU:

#. Convert the Pi0.5 model to OpenVINO as described in section :ref:`pi05_model_conversion`.

#. Run the following command to utilize OpenVINO command line ``benchmark_tool`` with the compressed Pi0.5 model:

   .. code-block:: bash

      benchmark_app -m pi05_lerobot_ov_ir_INT8/model.xml -hint latency -shape "images[1,1,3,224,224],img_masks[1,1],lang_tokens[1,200],lang_masks[1,200],state[1,32],actions[1,50,32]" -d CPU

Validation (Optional)
=====================

To validate the outputs of the model ensuring that model predictions are the same before and after OpenVINO optimization:

#. Ensure you have ran :file:`convert_pytorch_onnx.py` script (see :ref:`pi05_model_conversion`). This will generate a random input tensor and pass it through the original HuggingFace Pi0.5 model and save both the model input and output in the validation folder.

#. Run the :file:`validation/lerobot_ov_inferencing.py` file on the randomly generated input tensor from step 1. This will generate the model output for that tensor.

   .. code-block:: bash

      cd validation
      python lerobot_ov_inferencing.py

#. Run :file:`validation/is_same_tensor.py` and modify it to compare the original PyTorch Pi0.5 output and the OV optimized output tensors. MSE should be ``<1e-3`` showing that optimized model yields same predictions as the original PyTorch model.

   .. code-block:: bash

      python is_same_tensor.py
