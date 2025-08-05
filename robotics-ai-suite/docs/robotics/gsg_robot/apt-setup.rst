Set up the |lp_amr| APT Repositories
####################################

A target running a compatible OS can install Deb packages from hosted APT repositories.

.. figure:: ../images/system/target.png


This section explains the procedure to configure the APT package manager to use the hosted APT repositories.

Make sure that you have :doc:`prepared the system <prepare-system>`

#. Open a terminal prompt which will be used to execute the remaining steps.

#. Download the APT key to the system keyring:

   .. code-block:: bash

      wget -O- https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg | sudo tee /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null

#. Add the signed entry to |lp_amr| APT sources and configure the APT client to use the |lp_amr| APT repositories:

   .. code-block:: bash

      echo "deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee /etc/apt/sources.list.d/eci.list > /dev/null
      echo "deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee -a /etc/apt/sources.list.d/eci.list > /dev/null
      echo "deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://amrdocs.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) amr main" | sudo tee /etc/apt/sources.list.d/amr.list > /dev/null
      echo "deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://amrdocs.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) amr main" | sudo tee -a /etc/apt/sources.list.d/amr.list > /dev/null

#. Configure the |lp_amr| APT repository to have higher priority over other repositories:

   .. code-block:: bash

      echo -e "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" | sudo tee /etc/apt/preferences.d/isar
      echo -e "Package: *\nPin: origin amrdocs.intel.com\nPin-Priority: 1001" | sudo tee /etc/apt/preferences.d/amr

#. Configure the |lp_amr| APT repository to ignore FLANN 1.19 version

   .. code-block:: bash

      echo -e "\nPackage: libflann*\nPin: version 1.19.*\nPin-Priority: -1\n\nPackage: flann*\nPin: version 1.19.*\nPin-Priority: -1" | sudo tee -a /etc/apt/preferences.d/isar

#. Configure the APT repository of the |intel| |oneapi| Base Toolkit:

   .. code-block:: bash

      wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | sudo tee /usr/share/keyrings/oneapi-archive-keyring.gpg > /dev/null
      echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" | sudo tee /etc/apt/sources.list.d/oneAPI.list > /dev/null
      echo -e "Package: intel-oneapi-runtime-*\nPin: version 2024.1.*\nPin-Priority: 1001" | sudo tee /etc/apt/preferences.d/oneapi > /dev/null

   .. note::

      When operating behind a proxy you will need to add the proxy details to the ``gpg`` command.

      For Example:

      .. code-block:: bash

         sudo -E gpg --no-default-keyring --keyring /usr/share/keyrings/realsense-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --keyserver-options http-proxy=http://<proxy-server>:<port> --recv-keys F6E65AC044F831AC80A06380C8B3A55A6F3EFCDE


#. Continue the installation as described on page :doc:`install-openvino`.

