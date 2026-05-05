.. _model_cns:

Visual Servoing - CNS
#####################

Visual servoing, also known as vision-based robot control and abbreviated VS, is a technique which uses feedback information extracted from a vision sensor to control the motion of a robot. Visual Servoing control techniques are broadly classified into three types:

- Image-based (IBVS)
- Position/pose-based (PBVS)
- Hybrid approach

**IBVS** is based on the error between current and desired features on the image plane, and does not involve any estimate of the pose of the target. The features may be the coordinates of visual features, lines or moments of regions. 

**PBVS** is a model-based technique (with a single camera). This is because the pose of the object of interest is estimated with respect to the camera and then a command is issued to the robot controller, which in turn controls the robot. In this case the image features are extracted as well, but are additionally used to estimate 3D information (pose of the object in Cartesian space), hence it is servoing in 3D. 

**Hybrid** approaches use some combination of the 2D and 3D servoing. 

Here we take the **IBVS-based** Correspondence Encoded Neural Image Servo Policy as an example.

CNS Overview
=================

Correspondence encoded Neural image Servo policy (CNS) presents a graph neural network based solution for image servo utilizing explicit keypoints correspondence obtained from any detector-based feature matching methods, such as SIFT, AKAZE, ORB, SuperGlue and etc. 

It achieves <0.3° and sub-millimeter precision in real-world experiments (mean distance to target ≈ 0.275m) and runs in real-time (~40 fps with ORB as front-end).

.. .. image:: ../../assets/images/cns.png
   :width: 65%
   :align: center

**Model Architecture:**

- Input Representation: The model takes as input a pair of images: the current image captured by the robot's camera and a target image representing the desired view.
  
- Feature Extraction: The input images are processed through a convolutional neural network (CNN) to extract high-level visual features. This step is crucial for capturing the important visual information needed for the subsequent stages.

- Correspondence Encoding: The extracted features from both the current and target images are then used to compute visual correspondences. This involves identifying and encoding the relationships between features in the current image and their counterparts in the target image.

- Neural Network Layers: The encoded correspondences are fed into a series of neural network layers designed to learn the mapping from visual correspondences to control actions. These layers typically include fully connected layers that process the encoded information and produce the desired output.

- Control Output: The final output of the network is a set of control commands that guide the robot's motion to align the current view with the target view. These commands can include parameters such as translation and rotation adjustments.

**More Information:**

- Full paper: https://arxiv.org/abs/2309.09047
- Homepage: https://hhcaz.github.io/CNS-home
- Github link: https://github.com/hhcaz/CNS

Model Conversion
=================

CNS model can get an optimized inference performance on either Intel CPU or iGPU using OpenVINO toolkit. It is CPU-friendly and you can follow the `official installation tutorial <https://github.com/hhcaz/CNS>`_. It should be noted that ``PyTorch`` (>1.12) and ``PyTorch Geometric`` need to be installed compatibly, and ``pybullet-object-models`` is required when running demo_sim_Erender.py.

Installation guide of dependencies is as follows:

.. code-block:: bash
    
    # python library dependencies 
    pip install torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 --index-url https://download.pytorch.org/whl/xpu
    pip install tqdm numpy scipy pybullet matplotlib tensorboard scikit-image open3d>=0.12.0 opencv-python>=4.8.0 pyrealsense2==2.53.1.4623
    
    # install pybullet-object-models
    cd [path to your CNS project]/cns/thirdparty
    pip3 install -e pybullet-object-models/

Then, you can select CPU as the running device by:

.. code-block:: bash

    python3 demo_sim_Erender.py --device=CPU

Or directly change the device selection in demo code:

.. code-block:: python

    pipeline = CorrespondenceBasedPipeline(
        ...
        device="cpu",
        ...
    )

To run this model on Intel iGPU, you will need ``OpenVINO 2025.3.0`` and run the following conversion code in CNS project:

.. attention::
  OpenVINO 2025.3.0 will be released in early September 2025.

.. code-block:: python
    
      import openvino
      import torch
      from cns.benchmark.controller import GraphVSController
      from cns.models.graph_vs import GraphVS
      from cns.midend.graph_gen import GraphData
      import numpy as np
      
      # create OVGraphVS class based on original GraphVS
      class OVGraphVS(GraphVS):
          def __init__(self, *args, **kwargs):
              super().__init__(*args, **kwargs)

          def forward(self, x_cur, x_tar, pos_cur, pos_tar, l1_dense_edge_index_cur, l1_dense_edge_index_tar, l0_to_l1_edge_index_j_cur, l0_to_l1_edge_index_i_cur, cluster_mask, cluster_centers_index, num_clusters, new_scene, hidden=None, batch=None):
              l0_to_l1_edge_index_cur = torch.stack([l0_to_l1_edge_index_j_cur,
                                                     l0_to_l1_edge_index_i_cur], dim=0)

              if batch is None:
                  batch = torch.zeros(x_cur.size(0)).long().to(x_cur.device)
              
              x_clu = self.encoder(
                  x_cur, x_tar, pos_cur, pos_tar, cluster_mask, 
                  l0_to_l1_edge_index_cur, cluster_centers_index)
              pos_clu = pos_tar[cluster_centers_index]
              batch_clu = batch[cluster_centers_index]
              xx = self.init_hidden(num_clusters.sum()).to(x_cur)

              hidden = torch.where(new_scene, xx,hidden)
              
              hidden, x_clu = self.backbone(
                  hidden, x_clu, pos_clu, l1_dense_edge_index_cur, l1_dense_edge_index_tar, batch_clu)
              
              vel_si_vec, vel_si_norm = self.decoder(x_clu, cluster_mask, batch_clu)
              
              return vel_si_vec, vel_si_norm, hidden

      # generate example inputs
      example_input = {
          "x_cur": torch.rand(511, 2),
          "x_tar": torch.rand(511, 2),
          "pos_cur": torch.rand(511, 2),
          "pos_tar": torch.rand(511, 2),

          "l1_dense_edge_index_cur": torch.tensor([[ 0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  2,  2,  2,  2,  2,
                2,  2,  2,  2,  2,  2,  2,  2,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,
                3,  3,  3,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  5,  5,
                5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  6,  6,  6,  6,  6,  6,  6,
                6,  6,  6,  6,  6,  6,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
                7,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  9,  9,  9,  9,
                9,  9,  9,  9,  9,  9,  9,  9,  9, 10, 10, 10, 10, 10, 10, 10, 10, 10,
               10, 10, 10, 10, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 12,
               12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 13, 13, 13, 13, 13, 13,
               13, 13, 13, 13, 13, 13, 13],
              [ 0,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13,  0,  2,  3,  4,  5,
                6,  7,  8,  9, 10, 11, 12, 13,  0,  2,  3,  4,  5,  6,  7,  8,  9, 10,
               11, 12, 13,  0,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13,  0,  2,
                3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13,  0,  2,  3,  4,  5,  6,  7,
                8,  9, 10, 11, 12, 13,  0,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12,
               13,  0,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13,  0,  2,  3,  4,
                5,  6,  7,  8,  9, 10, 11, 12, 13,  0,  2,  3,  4,  5,  6,  7,  8,  9,
               10, 11, 12, 13,  0,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13,  0,
                2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13,  0,  2,  3,  4,  5,  6,
                7,  8,  9, 10, 11, 12, 13]]),

          "l1_dense_edge_index_tar": torch.tensor([[ 0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  1,  1,  1,
                1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  2,  2,  2,  2,  2,  2,  2,  2,
                2,  2,  2,  2,  2,  2,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,
                3,  3,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  5,  5,
                5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  6,  6,  6,  6,  6,  6,
                6,  6,  6,  6,  6,  6,  6,  6,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
                7,  7,  7,  7,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,
                9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9, 10, 10, 10, 10,
               10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 11, 11, 11, 11, 11, 11, 11, 11,
               11, 11, 11, 11, 11, 11, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12,
               12, 12, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13],
              [ 0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13,  0,  1,  2,  3,
                4,  5,  6,  7,  8,  9, 10, 11, 12, 13,  0,  1,  2,  3,  4,  5,  6,  7,
                8,  9, 10, 11, 12, 13,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11,
               12, 13,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13,  0,  1,
                2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13,  0,  1,  2,  3,  4,  5,
                6,  7,  8,  9, 10, 11, 12, 13,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9,
               10, 11, 12, 13,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13,
                0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13,  0,  1,  2,  3,
                4,  5,  6,  7,  8,  9, 10, 11, 12, 13,  0,  1,  2,  3,  4,  5,  6,  7,
                8,  9, 10, 11, 12, 13,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11,
               12, 13,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13]]),
          "l0_to_l1_edge_index_j_cur": torch.tensor([ 45, 372, 267, 268, 271, 277, 286, 295, 394, 395, 396, 413, 479, 476,
              501, 164, 165, 172, 323,   7,  17, 320, 324, 330, 352, 230, 253, 362,
              367, 454, 463, 495, 259, 307, 309, 312, 409, 415, 421, 424, 428, 474,
              478, 504, 190, 328, 336, 347, 436, 442, 486, 404, 423, 429, 337, 338,
              345, 231, 364, 365, 370, 492, 497, 507, 334, 432]),

          "l0_to_l1_edge_index_i_cur": torch.tensor([ 0,  0,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  3,  3,  4,  4,  4,
               4,  5,  5,  5,  5,  5,  6,  7,  7,  7,  7,  7,  7,  7,  8,  8,  8,  8,
               8,  8,  8,  8,  8,  8,  8,  8,  9,  9,  9,  9,  9,  9,  9, 10, 10, 10,
              11, 11, 11, 12, 12, 12, 12, 12, 12, 12, 13, 13]),

          "cluster_mask": torch.tensor([ True, False,  True,  True,  True,  True,  True,  True,  True,  True, True,  True,  True,  True]),
          "cluster_centers_index": torch.tensor([ 56,  64, 405, 131, 172, 174, 213, 244, 297, 340, 296, 437, 456, 485]),
          # batch = None
          "num_clusters": torch.tensor(14),
      }
      
      # Load checkpoint weights.
      ckpt=torch.load("checkpoints/cns_state_dict.pth", "cpu")
      if hasattr(ckpt, "net") and isinstance(ckpt["net"], torch.nn.Module):
          model: OVGraphVS = ckpt["net"]
      else:
          model = OVGraphVS(2, 2, 128, regress_norm=True).to("cpu")
          model.load_state_dict(ckpt)

      example_input["hidden"] = torch.rand(14,128)
      example_input["new_scene"] = torch.tensor(True)

      # Convert and Save IR model
      ov_model = openvino.convert_model(model, example_input=example_input)
      openvino.save_model(ov_model, "cns_ov/openvino_model.xml")
          
One simple inference run of CNS model on iGPU is as follows:

.. code-block:: python

    core = ov.Core()
    # set path to converted IR model
    model = "cns_ov/openvino_model.xml"
    # load model
    compiled_model = core.compile_model(model=model, device_name='GPU')
    # run inference with your example_input
    result_infer = compiled_model(example_input)
    # get result_infer
    print(result_infer)
