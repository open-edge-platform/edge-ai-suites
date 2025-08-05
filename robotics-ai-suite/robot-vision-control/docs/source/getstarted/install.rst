Install RVC
===========

Requirements
------------

1. |Docker_Engine| (Cannot be rootless, see `the installation <https://docs.docker.com/engine/install/ubuntu/>`_)

   * Docker version 20.10.0 or higher


2. Build Environment

   * Virtual Studio Code (VSCode) with Devcontainers extension (required)

Clone the repository
--------------------

To get started with the Robot Vision Control (RVC) project, you need to clone from the GitHub repository. Open a terminal and run the following command:

.. code-block:: bash

    $ git clone https://github.com/open-edge-platform/robotics-ai-suite.git

Open the folder ``robot-vision-control`` in VSCode and follow the instructions to open it in a devcontainer.
This will automatically build a container with all the required dependencies to run RVC.
The container is based on |Ubuntu_OS| 22.04 LTS (Jammy Jellyfish).

Build RVC image
-------------------
Build the RVC |docker| image outside of the devcontainer, after the devcontainer has been built. The Devcontainer provides the base container image for RVC.

.. code-block:: bash

   $ cd robotics-ai-suite/robot-vision-control
   $ ./docker_build_rvc_img.sh

Run RVC container
-----------------
After building the RVC image, you can run it using the following command:

.. code-block:: bash

   $ ./docker_run_rvc_img.sh

This will start a container named ``rvc`` and open a bash terminal inside it. The container is configured to use the host GPU and camera.
