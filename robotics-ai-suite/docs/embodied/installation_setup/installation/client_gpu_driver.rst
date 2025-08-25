Install Client GPUs driver
=============================

Installation
:::::::::::::::::::::::::::

The Ubuntu 22.04 repositories do not contain compute packages for various Intel graphics products. To install these packages, you can use Intel's dedicated package repository.

.. code-block:: bash

    # Install the Intel graphics GPG public key
    $ wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | \
    sudo gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics.gpg

    # Configure the repositories.intel.com package repository
    $ echo "deb [arch=amd64,i386 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy unified" | \
    sudo tee /etc/apt/sources.list.d/intel-gpu-jammy.list

    # Update the package repository metadata
    $ sudo apt update

    # Install the compute-related packages
    $ sudo apt-get install -y libze-intel-gpu1=24.52.32224.14-1077~22.04 libze1=1.19.2.0-1077~22.04 intel-opencl-icd=24.52.32224.14-1077~22.04 clinfo xpu-smi

The commands listed above install all the essential packages needed for most users, aiming to minimize the installation of unnecessary packages. However, certain scenarios may require you to install additional packages. If you plan to use PyTorch, install ``libze-dev`` and ``intel-ocloc`` additionally:

.. code-block:: bash

    $ sudo apt-get install -y libze-dev intel-ocloc

Verifying Installation
:::::::::::::::::::::::::::

To verify that the kernel and compute drivers are installed and functional, run ``clinfo``:

.. code-block:: bash

    $ clinfo | grep "Device Name"

You should see the Intel graphics product device names listed. If they do not appear, ensure you have permissions to access ``/dev/dri/renderD*``. This typically requires your user to be in the render group:

.. code-block:: bash

    $ sudo gpasswd -a ${USER} render
    $ newgrp render

To verify that the client GPUs drivers version (24.52.32224.14-1077~22.04):

.. code-block:: bash

    $ sudo apt-cache policy intel-opencl-icd

Alternatively, you can run the ``clinfo`` command as root.
