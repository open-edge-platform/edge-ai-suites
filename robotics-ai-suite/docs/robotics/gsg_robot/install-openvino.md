# Install OpenVINO™ Packages

## Add the OpenVINO™ APT repository

The following steps will add the OpenVINO™ APT repository to your package management.

1. Install the OpenVINO™ GPG key:

   ```bash
   wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | sudo tee /usr/share/keyrings/openvino-archive-keyring.gpg
   ```

2. Add the Deb package sources for OpenVINO™ 2025.
   This will allow you to choose your preferred OpenVINO™ version to be installed.

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

    ```bash
   echo "deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino/2025 ubuntu24 main" | sudo tee /etc/apt/sources.list.d/intel-openvino-2025.list
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

    ```bash
   echo "deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino/2025 ubuntu22 main" | sudo tee /etc/apt/sources.list.d/intel-openvino-2025.list
   ```

   <!--hide_directive:::
   ::::hide_directive-->

3. Run the following commands to create the file ``/etc/apt/preferences.d/intel-openvino``.

   This will pin the OpenVINO™ version to 2025.3.0. Earlier versions of OpenVINO™
   might not support inferencing on the NPU of Intel® Core™ Ultra processors.

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   echo -e "\nPackage: openvino-libraries-dev\nPin: version 2025.3.0*\nPin-Priority: 1001" | sudo tee /etc/apt/preferences.d/intel-openvino
   echo -e "\nPackage: openvino\nPin: version 2025.3.0*\nPin-Priority: 1001" | sudo tee -a /etc/apt/preferences.d/intel-openvino
   echo -e "\nPackage: ros-jazzy-openvino-wrapper-lib\nPin: version 2025.3.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino
   echo -e "\nPackage: ros-jazzy-openvino-node\nPin: version 2025.3.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   echo -e "\nPackage: openvino-libraries-dev\nPin: version 2025.3.0*\nPin-Priority: 1001" | sudo tee /etc/apt/preferences.d/intel-openvino
   echo -e "\nPackage: openvino\nPin: version 2025.3.0*\nPin-Priority: 1001" | sudo tee -a /etc/apt/preferences.d/intel-openvino
   echo -e "\nPackage: ros-humble-openvino-wrapper-lib\nPin: version 2025.3.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino
   echo -e "\nPackage: ros-humble-openvino-node\nPin: version 2025.3.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   If you decide to use a different OpenVINO™ version, ensure that all four packages
   (``openvino-libraries-dev``, ``openvino``, ``ros-jazzy-openvino-wrapper-lib``,
   and ``ros-jazzy-openvino-node``) are pinned to the same OpenVINO™ version.

## Install the OpenVINO™ Runtime and the ROS 2 OpenVINO™ Toolkit

The following steps will install the OpenVINO™ packages:

1. Ensure all APT repositories are updated:

   ```bash
   sudo apt update
   ```

2. Install the ``debconf-utilities``:

   ```bash
   sudo apt install debconf-utils
   ```

3. Clear any previous installation configurations:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   sudo apt purge ros-jazzy-openvino-node
   sudo apt autoremove -y
   echo PURGE | sudo debconf-communicate ros-jazzy-openvino-node
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   sudo apt purge ros-humble-openvino-node
   sudo apt autoremove -y
   echo PURGE | sudo debconf-communicate ros-humble-openvino-node
   ```

   <!--hide_directive:::
   ::::hide_directive-->

4. Install the OpenVINO™ Runtime:

   ```bash
   sudo apt install openvino
   ```

5. Install the the ROS 2 OpenVINO™ Toolkit:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   sudo apt install ros-jazzy-openvino-node
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   sudo apt install ros-humble-openvino-node
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   During the installation of the "openvino-node" package,
   you will be prompted to decide whether to install the OpenVINO™ IR
   formatted models.
   Since some tutorials in the Autonomous Mobile Robot, which are based on OpenVINO™,
   depend on these models; it is crucial to respond with 'yes' to this query.

   ![configure_ros-2-openvino-node](../images/configure_ros-humble-openvino-node.png)

6. Several Autonomous Mobile Robot tutorials allow you to perform OpenVINO™ inference
   on the integrated GPU device of Intel® processors. To enable this feature, install
   the Intel® Graphics Compute Runtime with the following command:

   ```bash
   sudo apt install -y libze1 libze-intel-gpu1
   ```

> **Note:** While you may encounter GPU driver installation guides that involve
> downloading ``*.deb`` files for manual installation, this method does not support
> automatic update. Therefore, it is advisable to install packages from an APT package
> feed for easier updates, as described above.

## OpenVINO™ Re-Installation and Troubleshooting

If you need to reinstall OpenVINO™ or clean your system after a failed
installation, run the following commands:

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
sudo apt purge ros-jazzy-openvino-node
sudo apt autoremove -y
echo PURGE | sudo debconf-communicate ros-jazzy-openvino-node
sudo apt install ros-jazzy-openvino-node
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
sudo apt purge ros-humble-openvino-node
sudo apt autoremove -y
echo PURGE | sudo debconf-communicate ros-humble-openvino-node
sudo apt install ros-humble-openvino-node
```

<!--hide_directive:::
::::hide_directive-->
