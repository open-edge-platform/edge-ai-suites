.. _model_dp:

Diffusion Policy
#################

Similar to the Action Chunking Transformer (ACT), the Diffusion Policy is another significant advancement in the field of robotic visuomotor policy learning, which represents policies as conditional denoising diffusion processes. This allows for effective handling of multimodal action distributions and is well adapted to high dimensional action spaces, which are common in robotic tasks. The algorithm's ability to learn the gradient of the action distribution score function and optimize via stochastic Langevin dynamics steps during inference provides a stable and efficient way to find optimal actions.

.. .. image:: ../../assets/images/dp.png
   :width: 85%
   :align: center

**Model Architecture:**

- The policy consists of a visual encoder (e.g., ResNet18 or ViT) to process visual observations and a diffusion model to generate actions.
- The diffusion model (e.g., FiLM conditioned U-Net or Transformer based) is trained to predict the noise added to the actions at each step of the diffusion process, conditioned on the visual observations.

**More Information:**

- Full paper: https://arxiv.org/abs/2303.04137v5
- Homepage: https://diffusion-policy.cs.columbia.edu/
- Github link: https://github.com/columbia-ai-robotics/diffusion_policy

Model Conversion
================
Diffusion Policy (DP) models are trained using **PyTorch**, but optimized inference performance on Intel devices can be achieved using **OpenVINO**. To enable this, PyTorch models should first be converted to **OpenVINO Intermediate Representation (IR)** format.

This document demonstrates how to convert DP model checkpoints to OpenVINO IR using the `low_dim transformer` and `image transformer` architectures as examples. The conversion process involves first converting the models to **ONNX**, followed by using OpenVINO’s `ovc` command-line tool to convert to IR format.

Model Checkpoints
-----------------

- **Low Dim Transformer DP model checkpoint**:  
  `epoch=0850-test_mean_score=0.967.ckpt <https://diffusion-policy.cs.columbia.edu/data/experiments/low_dim/pusht/diffusion_policy_transformer/train_0/checkpoints/epoch%3D0850-test_mean_score%3D0.967.ckpt>`_

- **Image Transformer DP model checkpoint**:  
  `epoch=0100-test_mean_score=0.748.ckpt <https://diffusion-policy.cs.columbia.edu/data/experiments/image/pusht/diffusion_policy_transformer/train_0/checkpoints/epoch%3D0100-test_mean_score%3D0.748.ckpt>`_

Low Dim Transformer DP Model KEY Conversion Steps
-------------------------------------------------

1. Load the Trained Checkpoint
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Checkpoint files contain model parameters saved during training. To prepare for conversion, rebuild the model structure and load the saved parameters:

.. code-block:: python

   ckpt = "data/new_data/lowdim_t967.ckpt"  # transformer
   payload = torch.load(open(ckpt, 'rb'), pickle_module=dill)

   # Read configuration from checkpoint
   cfg = payload['cfg']
   cls = hydra.utils.get_class(cfg._target_)

   # Instantiate model
   workspace = cls(cfg, output_dir=output_dir)
   print(f"cls: {cls}, workspace: {workspace}")

   # Load pretrained weights
   workspace.load_payload(payload, exclude_keys=None, include_keys=None)

   # Extract model
   policy = workspace.model

2. Prepare Model Wrapper for Export
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   class ConvertModel(torch.nn.Module):
       def __init__(self, policy):
           super(ConvertModel, self).__init__()
           self.policy = policy
           self.policy.model.eval()  # Set the internal model to evaluation mode

           # Wrapper for diffusion UNet model
           class ConvertUnetModel(torch.nn.Module):
               def __init__(self, policy):
                   super(ConvertUnetModel, self).__init__()
                   self.policy = policy
                   self.forward = self.forward_transformer

               def forward_transformer(self, trajectory, t, cond):
                   print("==> trajectory: ", trajectory.shape)
                   print("==> cond: ", cond.shape)
                   print("==> t: ", t.shape)
                   with torch.no_grad():
                       return self.policy.diffusion_unet_forward(trajectory, t, cond)

           self.convert_diffusion_unet = ConvertUnetModel(self.policy)

3. Define ONNX Export Function
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def export_onnx(self, output_dir, ckpt_name):
       """Exports the model components to ONNX format."""
       # Generate dummy inputs for exporting the observation encoder
       obs_dict = {
           "obs": torch.rand(1, 2, 20),
           "obs_mask": torch.rand(1, 2, 20),
       }
       self.policy.predict_action(obs_dict)  # obtain shapes of cond, cond_data, cond_mask

       # Prepare dummy inputs
       trajectory = torch.randn(1, 10, 2)
       t = torch.tensor([10], dtype=torch.float32)
       cond = torch.randn(1, 2, 20)

       export_name_unet = os.path.join(output_dir, f"{ckpt_name}_unet.onnx")
       unet_inputs = (trajectory, t, cond.detach())

       torch.onnx.export(
           self.convert_diffusion_unet,
           unet_inputs,
           export_name_unet,
           input_names=['trajectory', 't', 'cond'],
           export_params=True,
           opset_version=13,
           do_constant_folding=False,
       )
       print(f"[===] Diffusion UNet exported to {export_name_unet}")

4. Instantiate the Converter and Export Model
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   convert_model = ConvertModel(policy)
   convert_model.export_onnx(output_dir, ckpt_name)

5. Ensure OpenVINO is Installed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. note::

   Make sure OpenVINO is installed by following the official guide:  
   :ref:`Install OpenVINO via pip <openvino_install>`

6. Convert ONNX to OpenVINO IR Format
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Once the model is exported to ONNX, use OpenVINO’s `ovc` (OpenVINO Model Converter) to convert it to IR format:

.. code-block:: bash

   ovc lowdim_t967_unet.onnx

By default, the model will be converted to **FP16 IR format**. The following output files will be generated:

- `<model_name>.xml`: Defines the model topology.
- `<model_name>.bin`: Contains the model weights and binary data.


Image Transformer DP Model Key Conversion Steps
-------------------------------------------------

This guide outlines the steps to convert the Image Transformer model—including the observation encoder and diffusion model—into OpenVINO Intermediate Representation (IR) format.

1. Load the Trained Checkpoint
------------------------------

.. code-block:: python

   ckpt = "data/new_data/image_t748.ckpt"

   # Load checkpoint
   payload = torch.load(open(ckpt, 'rb'), pickle_module=dill)
   cfg = payload['cfg']

   cls = hydra.utils.get_class(cfg._target_)
   workspace = cls(cfg, output_dir=output_dir)

   print(f"cls: {cls}, workspace: {workspace}")

   # Load pre-trained weights
   workspace.load_payload(payload, exclude_keys=None, include_keys=None)

   # Access model
   policy = workspace.model  # Diffusion policy object, not a standard torch.nn.Module

2. Prepare Model Wrappers for Export
------------------------------------

Two components need to be wrapped for ONNX export: the observation encoder and the diffusion model.

.. code-block:: python

   import torch.nn as nn

   class ConvertModel(nn.Module):
       def __init__(self, policy):
           super().__init__()
           self.policy = policy
           self.policy.model.eval()
           self.policy.obs_encoder.eval()
           
           class ConvertObsEncoder(nn.Module):
               def __init__(self, policy):
                   super().__init__()
                   self.policy = policy

               def forward(self, agent_pos, image):
                   with torch.no_grad():
                       this_nobs = {'agent_pos': agent_pos, 'image': image}
                       return self.policy.obs_encoder_forward_onepass(this_nobs)

           class ConvertUnetModel(nn.Module):
               def __init__(self, policy):
                   super().__init__()
                   self.policy = policy
                   self.forward = self.forward_transformer

               def forward_transformer(self, trajectory, t, cond):
                   with torch.no_grad():
                       return self.policy.diffusion_unet_forward(trajectory, t, cond)

           self.convert_obs_encoder = ConvertObsEncoder(self.policy)
           self.convert_diffusion_unet = ConvertUnetModel(self.policy)

3. Define ONNX Export Function
------------------------------

.. code-block:: python

   def export_onnx(self, output_dir, ckpt_name):
       agent_pos = torch.rand(2, 2)
       image = torch.rand(2, 3, 96, 96)

       export_name_obs_encoder = os.path.join(output_dir, f"{ckpt_name}_obs_encoder_onepass.onnx")
       torch.onnx.export(
           self.convert_obs_encoder,
           args=(agent_pos, image),
           f=export_name_obs_encoder,
           export_params=True,
           opset_version=13,
           do_constant_folding=True,
       )
       print(f"[===] Obs Encoder exported to {export_name_obs_encoder}")


       trajectory = torch.rand(1, 10, 2)
       cond = torch.rand(1, 2, 66)
       t = torch.tensor([10], dtype=torch.float32)

       export_name_unet = os.path.join(output_dir, f"{ckpt_name}_unet_onepass.onnx")
       unet_inputs = (trajectory, t, cond.detach())

       torch.onnx.export(
           self.convert_diffusion_unet,
           unet_inputs,
           export_name_unet,
           input_names=['trajectory', 't', 'cond'],
           export_params=True,
           opset_version=13,
           do_constant_folding=True,
       )
       print(f"[===] Diffusion UNet exported to {export_name_unet}")

4. Instantiate the Converter and Export the Model
-------------------------------------------------

.. code-block:: python

   convert_model = ConvertModel(policy)
   convert_model.export_onnx(output_dir, ckpt_name)

5. Install OpenVINO
-------------------

.. note::

   Ensure that OpenVINO is installed. Follow the official installation guide:  
   `Install OpenVINO via pip <https://docs.openvino.ai/2025/get-started/install-openvino/install-openvino-pip.html>`_

6. Convert ONNX to OpenVINO IR
------------------------------

Use OpenVINO’s Model Optimizer (`ovc`) to convert the exported ONNX models to IR format.

.. code-block:: bash

   ovc image_t748_obs_encoder_onepass.onnx
   ovc image_t748_unet_onepass.onnx