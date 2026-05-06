This section explains the procedure to configure the APT package manager to use the hosted ECI APT repository.

Make sure that you have the right [OS Setup](os_setup.md).

# Set up ECI APT Repository

1. Open a terminal prompt which will be used to execute the remaining steps.

2. Download the ECI APT key to the system keyring:

   ```bash
   sudo -E wget -O- https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg | sudo tee /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null
   ```

3. Add the signed entry to APT sources and configure the APT client to use the ECI APT repository:

   ```bash
   echo "deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee /etc/apt/sources.list.d/eci.list
   echo "deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee -a /etc/apt/sources.list.d/eci.list
   ```

   **Note**: The auto upgrade feature in Canonical Ubuntu will change the deployment environment over time. If you do not want to auto upgrade, execute the following commands to disable the feature:

   ```bash
   sudo sed -i "s/APT::Periodic::Update-Package-Lists \"1\"/APT::Periodic::Update-Package-Lists \"0\"/g" "/etc/apt/apt.conf.d/20auto-upgrades"
   sudo sed -i "s/APT::Periodic::Unattended-Upgrade \"1\"/APT::Unattended-Upgrade \"0\"/g" "/etc/apt/apt.conf.d/20auto-upgrades"
   ```

4. Configure the ECI APT repository to have higher priority over other repositories:

   ```bash
   sudo bash -c 'echo -e "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" >> /etc/apt/preferences.d/isar'
   sudo bash -c 'echo -e "Package: libze-intel-gpu1,libze1,intel-opencl-icd,libze-dev,intel-ocloc\nPin: origin repositories.intel.com/gpu/ubuntu\nPin-Priority: 1000" >> /etc/apt/preferences.d/isar'
   ```

# Set up ROS2 APT Repository

1. Ensure that the [Ubuntu Universe repository](https://help.ubuntu.com/community/Repositories/Ubuntu) is enabled.

   ```bash
   sudo apt install software-properties-common
   sudo add-apt-repository universe
   ```

2. Add the ROS 2 GPG key with apt.

   ```bash
   sudo apt update && sudo apt install curl -y
   sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
   ```

   **Note**: If your DNS cannot resolve `raw.githubusercontent.com`, modify the `/etc/hosts` file to directly connect to the `raw.githubusercontent` server:

   ```bash
   sudo bash -c "echo '185.199.108.133 raw.githubusercontent.com' >> /etc/hosts"
   ```

3. Add the repository to your sources list.

   ```bash
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
   ```

4. Update your apt repository caches after setting up the repositories.

   ```bash
   sudo apt update
   ```
