.. _diffusion_policy:

Diffusion Policy
#################

Diffusion Policy presents an innovative method for generating robot actions by conceptualizing visuomotor policy learning as a conditional denoising diffusion process. During inference, it utilizes the gradient of the score function for the action distribution and applies iterative stochastic Langevin dynamics, allowing for robust management of complex, multimodal, and high-dimensional action spaces while maintaining training stability. Key features, including receding horizon control, visual input conditioning, and a time-series diffusion transformer, further enhance the effectiveness of this approach for real-world visuomotor policy learning.

A diffusion policy pipeline is provided for evaluating the diffusion policy model on the ``Push-T`` task in simulation. This pipeline includes source code optimized with |OpenVINO| for improved performance, and supports both Transformer-based and CNN-based diffusion policy for inference on the ``Push-T`` task.

In this tutorial, we will introduce how to setup Diffusion Policy simulation pipeline.

Simulation Task
===============

Push-T
:::::::

The Push-T task is a manipulation task where the robot must push a T-shaped block to a target location. The block is gray, the target is green, and the robot's End-Effector is represented by a blue circular shape. The task includes variations in initial conditions for both the T block and the End-Effector, requiring the robot to exploit complex and contact-rich object dynamics to achieve precise positioning of the T block using point contacts.

There are two variants with proprioception for End-Effector location:

* image : one with RGB image observations
* low-dim : another with 9 2D keypoints obtained from the ground-truth pose of the T block

The maximum step of the task is 300, and the reward is defined as the maximum overlap between the target position and the T-shaped block during the pushing process.

.. image:: assets/images/dp-task-pusht.gif
   :width: 35%
   :align: center

Prerequisites
=============

Please make sure you have finished setup steps in :doc:`../installation_setup`.

Installation
=============

Install Diffusion Policy package
:::::::::::::::::::::::::::::::::

The Embodied Intelligence SDK provides optimized source code for Intel® OpenVINO™. To get the source code from ``/opt/diffusion-policy-ov/`` with the following command:

.. code-block:: bash

    $ sudo apt install diffusion-policy-ov
    $ sudo chown -R $USER /opt/diffusion-policy-ov/

After installing the ``diffusion-policy-ov`` package, follow the ``README.md`` file in ``/opt/diffusion-policy-ov/`` to set up the complete source code environment.

Virtual environment setup
:::::::::::::::::::::::::

Download and install the ``Miniforge`` as follows if you don't have conda installed on your machine:

.. code-block:: bash

    $ wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
    $ bash Miniforge3-Linux-x86_64.sh
    $ source ~/.bashrc

You can use ``conda --version`` to verify you conda installation.
After installation, create a new python environment ``robodiff``:

.. code-block:: bash

    $ cd <diffusion-policy_SOURCE_CODE_PATH>
    $ mamba env create -f conda_environment.yaml

After installation, activate the ``robodiff`` Python environment in your current terminal:

.. code-block:: bash

    $ conda activate robodiff

Install |OpenVINO|
::::::::::::::::::::

Install the |OpenVINO| with the following command:

.. code-block:: bash

    $ pip install huggingface_hub==0.24.7 openvino==2024.6

Run pipeline
=============

Inference
:::::::::

1. Refer to ``<diffusion-policy_SOURCE_CODE_PATH>/ov_convert/README.md`` for instructions on downloading the pre-trained checkpoints, there are four available checkpoints for Push-T task.

.. note::

    For detailed instructions on the model conversion process, please refer to the model tutorial at :doc:`../developer_tools_tutorials/model_tutorials/model_dp`.

.. list-table::
   :widths: 15 30 15 20 20
   :header-rows: 1

   * - Item
     - Pre-trained checkpoint Name
     - Low-dim or image
     - Policy
     - Parameters
   * - ``lowdim_t967.ckpt``
     - ``epoch=0850-test_mean_score=0.967.ckpt``
     - low-dim
     - diffusion policy transformer
     - 8.96M
   * - ``lowdim_c969.ckpt``
     - ``epoch=0550-test_mean_score=0.969.ckpt``
     - low-dim
     - diffusion policy CNN
     - 65.25M
   * - ``image_t748.ckpt``
     - ``epoch=0100-test_mean_score=0.748.ckpt``
     - image
     - diffusion policy transformer
     - 20.18M
   * - ``image_c884.ckpt``
     - ``epoch=0500-test_mean_score=0.884.ckpt``
     - image
     - diffusion policy CNN
     - 262.71M

2. Refer to ``<diffusion-policy_SOURCE_CODE_PATH>/ov_convert/README.md`` for instructions on converting the model checkpoint to OpenVINO IR format.

.. attention::

    You need to set the ``--output_dir`` to save the converted model to ``~/ov_models/pushT/`` directory.

The expectation result of this step is that you will have the following files in ``~/ov_models/pushT/`` directory:

.. code-block:: bash

    $ ls ~/ov_models/pushT/ -l
    -rw-rw-r-- ... image_c884_obs_encoder_onepass.bin
    -rw-rw-r-- ... image_c884_obs_encoder_onepass.xml
    -rw-rw-r-- ... image_c884_unet_onepass.bin
    -rw-rw-r-- ... image_c884_unet_onepass.xml
    -rw-rw-r-- ... image_t748_obs_encoder_onepass.bin
    -rw-rw-r-- ... image_t748_obs_encoder_onepass.xml
    -rw-rw-r-- ... image_t748_unet_onepass.bin
    -rw-rw-r-- ... image_t748_unet_onepass.xml
    -rw-rw-r-- ... lowdim_c969_unet.bin
    -rw-rw-r-- ... lowdim_c969_unet.xml
    -rw-rw-r-- ... lowdim_t967_unet.bin
    -rw-rw-r-- ... lowdim_t967_unet.xml

3. You can run the inference with the following command:

.. attention::

    * You need to set the ``--checkpoint`` to select the pre-trained checkpoint because it contains the policy model configuration.
    * You need to set the ``--output_dir`` to save the inference results.
    * You can set the ``--seed`` to control the randomness of the inference; the default value is 4300000.
    * For converted OpenVINO IR, you don't need to set the model path since the default load directory is ``~/ov_models/pushT/``.

.. code-block:: bash

    $ conda activate robodiff
    $ cd <diffusion-policy_SOURCE_CODE_PATH>
    $ python eval.py --checkpoint <Pre-Trained_ckpt_PATH> --output_dir <output_dir>

4. The inference results will be saved in the ``<output_dir>`` directory, which contains the following files:

.. code-block:: bash

    $ ls <output_dir> -l
    -rw-rw-r-- ... eval_log.json
    drwxrwxr-x ... media

The ``eval_log.json`` contains the evaluation results, and the ``media`` directory contains the video of the inference process.
