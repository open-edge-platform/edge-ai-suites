.. _model_idp3:

Improved 3D Diffusion Policy (iDP3)
###################################

Improved 3D Diffusion Policy (iDP3) builds upon the original Diffusion Policy framework by enhancing its capabilities for 3D robotic manipulation tasks. The original Diffusion Policy, while effective for 2D tasks, faced challenges in scaling to 3D environments due to increased complexity and the need for more accurate spatial reasoning. Instead, to address the limitations of the original framework, iDP3 uses a more sophisticated 3D visual encoder to point clouds, enabling the policy to better understand the 3D structure of the environment.

**Model Architecture:**

- A 3D visual encoder to process point clouds.
- A diffusion model that generates actions conditioned on the encoded visual features.
- A temporal module to incorporate past observations and actions for smoother trajectory generation.
- The diffusion model is trained to iteratively denoise actions, starting from random noise and refining them into precise, task-relevant actions.

**More Information:**

- Full paper: https://arxiv.org/abs/2410.10803
- Homepage: https://humanoid-manipulation.github.io/
- Github link: https://github.com/YanjieZe/Improved-3D-Diffusion-Policy

Model Conversion
================

iDP3 Model Key Conversion Steps  
--------------------------------
This guide outlines the steps to convert the **iDP3** improved 3D Point Cloud Diffusion Policy model—including the observation encoder and diffusion model—into OpenVINO Intermediate Representation (IR) format.

1. Load the Trained Checkpoint  
------------------------------

.. code-block:: python

   import hydra
   import torch
   import dill
   import os

   ckpt = "latest.ckpt"
   ckpt_name = ckpt.split("/")[-1].split(".ckpt")[0]
   output_dir = "onnx_ckpt"
   os.makedirs(output_dir, exist_ok=True)

   # Load checkpoint
   payload = torch.load(open(ckpt, 'rb'), pickle_module=dill)
   cfg = payload['cfg']
   cfg._target_ = "diffusion_policy_3d.workspace.idp3_workspace.iDP3Workspace"

   cls = hydra.utils.get_class(cfg._target_)
   workspace = cls(cfg, output_dir=output_dir)
   workspace.load_checkpoint(ckpt)
   # Access model
   policy = workspace.model  # Diffusion policy object

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

               def forward(self, agent_pos, point_cloud):
                   with torch.no_grad():
                       obs_dict = {"agent_pos": agent_pos, "point_cloud": point_cloud}
                       return self.policy.obs_encoder.forward(obs_dict)

           class ConvertUnetModel(nn.Module):
               def __init__(self, policy):
                   super().__init__()
                   self.policy = policy
                   self.forward = self.forward_cnn

               def forward_cnn(self, trajectory, t, global_cond, local_cond):
                   with torch.no_grad():
                       return self.policy.diffusion_unet_forward(trajectory, t, global_cond, local_cond)

           self.convert_obs_encoder = ConvertObsEncoder(self.policy)
           self.convert_diffusion_unet = ConvertUnetModel(self.policy)

3. Define ONNX Export Function  
------------------------------

.. code-block:: python

   @torch.no_grad()
   def export_onnx(self, output_dir, ckpt_name):
       agent_pos = torch.rand(1, 32)
       point_cloud = torch.rand(1, 4096, 3)
       local_cond = None

       export_name_obs_encoder = os.path.join(output_dir, f"{ckpt_name}_obs_encoder.onnx")
       torch.onnx.export(
           self.convert_obs_encoder,
           (agent_pos, point_cloud),
           export_name_obs_encoder,
           input_names=['agent_pos', 'point_cloud'],
           export_params=True,
           opset_version=13,
           do_constant_folding=True,
       )
       print(f"[===] Obs Encoder exported to {export_name_obs_encoder}")

       trajectory = torch.randn(1, 16, 25)
       t = torch.randint(100, size=(1,)).float()
       global_cond = torch.randn(1, 384)

       export_name_unet = os.path.join(output_dir, f"{ckpt_name}_unet.onnx")
       torch.onnx.export(
           self.convert_diffusion_unet,
           (trajectory, t, global_cond, local_cond),
           export_name_unet,
           input_names=['trajectory', 't', 'global_cond', 'local_cond'],
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
   `Install OpenVINO 2025.2 via pip <https://docs.openvino.ai/2025/get-started/install-openvino.html?PACKAGE=OPENVINO_BASE&VERSION=v_2025_2_0&OP_SYSTEM=LINUX&DISTRIBUTION=PIP>`_

6. Convert ONNX to OpenVINO IR  
------------------------------

Use OpenVINO’s Model Optimizer (`ovc`) to convert the exported ONNX models to IR format.

.. code-block:: bash

   ovc latest_obs_encoder.onnx
   ovc latest_unet.onnx

Install and Locate Source Code
==============================
After running ``sudo apt install idp3-ov``, you will be able to see the source code under the ``/opt/idp3-ov/`` directory, follow the ``README.md`` file in ``/opt/idp3-ov/`` to set up the complete source code environment.