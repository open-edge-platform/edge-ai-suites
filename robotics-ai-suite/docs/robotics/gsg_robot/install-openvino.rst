Install |openvino| Packages
###########################

.. _openvino_installation_steps:

Add the |openvino| APT repository
---------------------------------

The following steps will add the |openvino| APT repository to your package management.

#. Install the |openvino| GPG key:

   .. code-block:: bash

      wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | sudo tee /usr/share/keyrings/openvino-archive-keyring.gpg

#. Add the |deb_pack| sources for |openvino| 2023 and |openvino| 2024.
   This will allow you to choose your preferred |openvino| version to be installed.

   .. code-block:: bash

      echo "deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino/2023 ubuntu22 main" | sudo tee /etc/apt/sources.list.d/intel-openvino-2023.list
      echo "deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino/2024 ubuntu22 main" | sudo tee /etc/apt/sources.list.d/intel-openvino-2024.list

#. Run the following commands to create the file ``/etc/apt/preferences.d/intel-openvino``.
   This will pin the |openvino| version to 2024.2.0. Earlier versions of |openvino| might
   not support inferencing on the NPU of |core| Ultra processors.

   .. code-block:: bash

      echo -e "\nPackage: openvino-libraries-dev\nPin: version 2024.2.0*\nPin-Priority: 1001" | sudo tee /etc/apt/preferences.d/intel-openvino
      echo -e "\nPackage: openvino\nPin: version 2024.2.0*\nPin-Priority: 1001" | sudo tee -a /etc/apt/preferences.d/intel-openvino
      echo -e "\nPackage: ros-humble-openvino-wrapper-lib\nPin: version 2024.2.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino
      echo -e "\nPackage: ros-humble-openvino-node\nPin: version 2024.2.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino

   If you decide to use a different |openvino| version, ensure that all four packages
   (``openvino-libraries-dev``, ``openvino``, ``ros-humble-openvino-wrapper-lib``,
   and ``ros-humble-openvino-node``) are pinned to the same |openvino| version.


Install the |openvino| Runtime and the |ros| |openvino| Toolkit
---------------------------------------------------------------

The following steps will install the |openvino| packages:

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

#. Install the |openvino| Runtime:

   .. code-block:: bash

      sudo apt install openvino

#. Install the the |ros| |openvino| Toolkit:

   .. code-block:: bash

      sudo apt install ros-humble-openvino-node

   During the installation of the ``ros-humble-openvino-node`` package,
   you will be prompted to decide whether to install the |openvino| IR
   formatted models.
   Since some tutorials in the |lp_amr|, which are based on |openvino|,
   depend on these models; it is crucial to respond with 'yes' to this query.

   .. image:: ../images/configure_ros-humble-openvino-node.png
      
#. Several |p_amr| tutorials allow you to perform |openvino| inference on the integrated GPU device of |intel| processors. 
   To enable this feature, install the |intel| Graphics Compute Runtime with the following command:
   
   .. code-block:: bash

      sudo apt install -y libze1 libze-intel-gpu1

   .. Note:: While you may encounter GPU driver installation guides that involve downloading ``*.deb`` files for manual installation, 
      this method does not support automatic update. Therefore, it is advisable to install packages from an APT package feed for easier updates, 
      as described above. 

.. _openvino_installation_cleanup_steps:

|openvino| Re-Installation and Troubleshooting
----------------------------------------------

If you need to reinstall |openvino| or clean your system after a failed
installation, run the following commands:

.. code-block:: bash

   sudo apt purge ros-humble-openvino-node
   sudo apt autoremove -y
   echo PURGE | sudo debconf-communicate ros-humble-openvino-node
   sudo apt install ros-humble-openvino-node
