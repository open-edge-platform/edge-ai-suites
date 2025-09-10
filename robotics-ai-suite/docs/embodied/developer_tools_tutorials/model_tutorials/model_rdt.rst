.. _model_rdt:

Robotics Diffusion Transformer (RDT-1B)
########################################

Robotics Diffusion Transformer with 1.2B parameters (RDT-1B), is a diffusion-based foundation model for robotic manipulation. It is pre-trained on a multi-robot collection of 46 datasets with 1M+ episodes. To boost bimanual capability, RDT-1B have collected 6K+ episodes (one of the largest to date) on the ALOHA dual-arm robot for fine-tuning. It has set a new benchmark in terms of dexterity, zero-shot generalizability, and few-shot learning. It supports control of almost all modern manipulators (e.g., dual-arm, joints, EEFs, and even wheeled locomotion) and is ready for the community to fine-tune with their robots.

.. .. image:: ../../assets/images/rdt-1b.png
   :width: 85%
   :align: center

**Model Architecture:**

- Vision encoder (SigLIP): Processes visual input (e.g., images or video) to understand the environment and objects.

- Language encoder (T5-XXL): Interprets natural language instructions to determine the task goals.

- Action encoder (MLP): encode low-dimensional vectors that represent physical quantities of the robot, including the proprioception, the action chunk, and the control frequency.

- Action Module (Diffusion Transformer): Generates and executes robotic actions (e.g., grasping, moving) based on the integrated understanding of vision and language.

**More Information:**

- Full paper: https://arxiv.org/pdf/2410.07864
- Homepage: https://rdt-robotics.github.io/rdt-robotics/
- Github link: https://huggingface.co/robotics-diffusion-transformer/rdt-1b

Model Conversion
================

| RDT-1B model is consists of several components, the conversion process involves exporting these components to |OpenVINO| IR format.
| The conversion python script and jupyter notebook are available, please refer to :ref:`Sample Pipeline - RDT Installation <rdt_installation>` to get installation and environment ready.  
| You can download a `pre-trained RDT-1B weights <https://hf-mirror.com/robotics-diffusion-transformer/rdt-1b>`_ from the Hugging Face Hub.

Convert by Script
-------------------

| Converting by script is recommended when you want to get the |OpenVINO| IR format quickly. 
| Simply run the following command at project directory to convert the pre-trained RDT-1B model to |OpenVINO| IR format:

.. code-block:: bash

   $ python -m scripts.convert.ov_convert --pretrained <pretrained_rdt_model_path> --output_dir <output_dir> 


- ``<pretrained_rdt_model_path>``: The path to the pre-trained RDT-1B model.
- ``<output_dir>``: (optional) The directory where the converted OpenVINO IR files will be saved. Default is `ov_ir`.


Convert by Jupyter Notebook
-----------------------------

| Converting by Jupyter Notebook is recommended when you want to understand the conversion process step by step, or if you want to modify the conversion parameters.
| The notebook provides a step-by-step guide to load the pre-trained model and convert several components into |OpenVINO| IR format.

You can find the notebook in the same directory as the conversion script. Open it in Jupyter Notebook or JupyterLab, and follow the instructions provided within the notebook to perform the conversion.


.. note::

   If you are using docker container built from the `Dockerfile` in the project, you can skip step #1 & #2 as the environment is already set up.


#. Install Jupyter Notebook and ipywidgets:

   .. code-block:: bash

      $ pip install notebook ipywidgets

#. Add your environment in ipykernel:

   .. code-block:: bash

      $ python -m ipykernel install --user --name <your_env_name> --display-name <name_displayed_in_jupyter>

#. Launch Jupyter Notebook:

   .. code-block:: bash

      $ jupyter notebook --notebook-dir <path_to_your_project>/scripts/convert  --ip <your_ip_address> --port <your_port>

