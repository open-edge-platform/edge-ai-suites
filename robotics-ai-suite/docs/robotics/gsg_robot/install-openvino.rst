Install OpenVINO™ Packages
###########################

.. _openvino_installation_steps:

Add the OpenVINO™ APT repository
---------------------------------

The following steps will add the OpenVINO™ APT repository to your package management.

#. Install the OpenVINO™ GPG key:

   .. code-block:: bash

      wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | sudo tee /usr/share/keyrings/openvino-archive-keyring.gpg

#. Add the Deb package sources for OpenVINO™ 2023 and OpenVINO™ 2024.
   This will allow you to choose your preferred OpenVINO™ version to be installed.

   .. code-block:: bash

      echo "deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino/2023 ubuntu22 main" | sudo tee /etc/apt/sources.list.d/intel-openvino-2023.list
      echo "deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino/2024 ubuntu22 main" | sudo tee /etc/apt/sources.list.d/intel-openvino-2024.list

#. Run the following commands to create the file ``/etc/apt/preferences.d/intel-openvino``.
   This will pin the OpenVINO™ version to 2024.2.0. Earlier versions of OpenVINO™ might
   not support inferencing on the NPU of Intel® Core™ Ultra processors.

   .. code-block:: bash

      echo -e "\nPackage: openvino-libraries-dev\nPin: version 2024.2.0*\nPin-Priority: 1001" | sudo tee /etc/apt/preferences.d/intel-openvino
      echo -e "\nPackage: openvino\nPin: version 2024.2.0*\nPin-Priority: 1001" | sudo tee -a /etc/apt/preferences.d/intel-openvino
      echo -e "\nPackage: ros-humble-openvino-wrapper-lib\nPin: version 2024.2.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino
      echo -e "\nPackage: ros-humble-openvino-node\nPin: version 2024.2.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino

   If you decide to use a different OpenVINO™ version, ensure that all four packages
   (``openvino-libraries-dev``, ``openvino``, ``ros-humble-openvino-wrapper-lib``,
   and ``ros-humble-openvino-node``) are pinned to the same OpenVINO™ version.


Install the OpenVINO™ Runtime and the ROS 2 OpenVINO™ Toolkit
---------------------------------------------------------------

The following steps will install the OpenVINO™ packages:

#. Ensure all APT repositories are updated:

   .. code-block:: bash

      sudo apt update

#. Install the ``debconf-utilities``:

   .. code-block:: bash

      sudo apt install debconf-utils

#. Clear any previous installation configurations:

   .. code-block:: bash

      sudo apt purge ros-humble-openvino-node
      sudo apt autoremove -y
      echo PURGE | sudo debconf-communicate ros-humble-openvino-node

#. Install the OpenVINO™ Runtime:

   .. code-block:: bash

      sudo apt install openvino

#. Install the the ROS 2 OpenVINO™ Toolkit:

   .. code-block:: bash

      sudo apt install ros-humble-openvino-node

   During the installation of the ``ros-humble-openvino-node`` package,
   you will be prompted to decide whether to install the OpenVINO™ IR
   formatted models.
   Since some tutorials in the Autonomous Mobile Robot, which are based on OpenVINO™,
   depend on these models; it is crucial to respond with 'yes' to this query.

   .. image:: ../images/configure_ros-humble-openvino-node.png

#. Several Autonomous Mobile Robot tutorials allow you to perform OpenVINO™ inference on the integrated GPU device of Intel® processors.
   To enable this feature, install the Intel® Graphics Compute Runtime with the following command:

   .. code-block:: bash

      sudo apt install -y libze1 libze-intel-gpu1

   .. Note:: While you may encounter GPU driver installation guides that involve downloading ``*.deb`` files for manual installation,
      this method does not support automatic update. Therefore, it is advisable to install packages from an APT package feed for easier updates,
      as described above.

.. _openvino_installation_cleanup_steps:

OpenVINO™ Re-Installation and Troubleshooting
----------------------------------------------

If you need to reinstall OpenVINO™ or clean your system after a failed
installation, run the following commands:

.. code-block:: bash

   sudo apt purge ros-humble-openvino-node
   sudo apt autoremove -y
   echo PURGE | sudo debconf-communicate ros-humble-openvino-node
   sudo apt install ros-humble-openvino-node
