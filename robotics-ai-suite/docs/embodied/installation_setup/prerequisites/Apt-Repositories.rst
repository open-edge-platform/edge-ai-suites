This section explains the procedure to configure the APT package manager to use the hosted ECI APT repository.

Make sure that you have the right :ref:`OS Setup <Os_Setup>`.

Set up ECI APT Repository
^^^^^^^^^^^^^^^^^^^^^^^^^^

#. Open a terminal prompt which will be used to execute the remaining steps.

#. Download the ECI APT key to the system keyring:

   .. code-block:: bash

      $ sudo -E wget -O- https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg | sudo tee /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null

#. Add the signed entry to APT sources and configure the APT client to use the ECI APT repository:

   .. code-block:: bash

      $ echo "deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee /etc/apt/sources.list.d/eci.list
      $ echo "deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee -a /etc/apt/sources.list.d/eci.list


   **Note**: The auto upgrade feature in |Ubuntu| will change the deployment environment over time. If you do not want to auto upgrade, execute the following commands to disable auto upgrade:

   .. code-block:: bash

      $ sudo sed -i "s/APT::Periodic::Update-Package-Lists \"1\"/APT::Periodic::Update-Package-Lists \"0\"/g" "/etc/apt/apt.conf.d/20auto-upgrades"
      $ sudo sed -i "s/APT::Periodic::Unattended-Upgrade \"1\"/APT::Unattended-Upgrade \"0\"/g" "/etc/apt/apt.conf.d/20auto-upgrades"

#. Configure the ECI APT repository to have higher priority over other repositories:

   .. code-block:: bash

      $ sudo bash -c 'echo -e "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" >> /etc/apt/preferences.d/isar'
      $ sudo bash -c 'echo -e "Package: libze-intel-gpu1,libze1,intel-opencl-icd,libze-dev,intel-ocloc\nPin: origin repositories.intel.com/gpu/ubuntu\nPin-Priority: 1000" >> /etc/apt/preferences.d/isar'


Set up ROS2 APT Repository
^^^^^^^^^^^^^^^^^^^^^^^^^^^

#. First ensure that the `Ubuntu Universe repository <https://help.ubuntu.com/community/Repositories/Ubuntu>`_ is enabled.

   .. code-block:: bash

     $ sudo apt install software-properties-common
     $ sudo add-apt-repository universe

#. Now add the ROS 2 GPG key with apt.

   .. code-block:: bash

     $ sudo apt update && sudo apt install curl -y
     $ sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg

  **Note**: If your DNS cannot resolute ``raw.githubusercontent.com``, modify the ``/etc/host`` file to directly connect to the ``raw.githubusercontent`` server:

  .. code-block:: bash

     $ sudo bash -c "echo '185.199.108.133 raw.githubusercontent.com' >> /etc/hosts"

#. Then add the repository to your sources list.

   .. code-block:: bash

     $ echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

#. Update your apt repository caches after setting up the repositories.

   .. code-block:: bash

     $ sudo apt update
