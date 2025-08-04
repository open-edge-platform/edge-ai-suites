      .. list-table::
         :widths: 20 40 50
         :header-rows: 1

         * - Component Group 
           - Package
           - Description
         * - :ref:`LinuxBSP <linuxbsp>`
           - | linux-intel-rt-experimental
             | linux-intel-experimental
           - Intel's |Linux| LTS real-time kernel (preempt-rt) and generic kernel, kernel version is 6.12.8
         * - `Linux Runtime Optimization <https://eci.intel.com/docs/3.3/appendix.html#eci-kernel-boot-optimizations>`__
           - customizations-grub
           - |Linux| ECI and IOTG GRUB Customization
         * - `Linux firmware <https://eci.intel.com/docs/3.3/development/tutorials/enable-graphics.html>`__
           - linux-firmware
           - |Linux| firmware with Ultra iGPU firmware
         * - :ref:`EtherCAT Master Stack <ethercat>`
           - | ighethercat
             | ighethercat-dpdk
             | ighethercat-dkms
             | ighethercat-examples
             | ighethercat-dpdk-examples
             | ecat-enablekit
             | ecat-enablekit-dpdk
           - Optimized open source IgH EtherCAT Master Stack, it supports on kernel space and user space  
         * - `Motion Control Gateway <https://eci.intel.com/docs/3.3/development/tutorials/enable-ros2-motion-ctrl-gw.html>`__
           - | rt-data-agent
             | ros-humble-agvm
             | ros-humble-agvm-description
             | ros-humble-agvm-joystick
             | ros-humble-agvm-nav2-helper
             | ros-humble-agvm-plcshm
             | ros-humble-agvm-plcshm-acrn
             | ros-humble-grasp-msgs
             | ros-humble-grasp-ros2
             | ros-humble-hiwin-ra605-710-gb-support
             | ros-humble-hiwin-robot-moveit-config
             | ros-humble-hiwin-xeg-16-support
             | ros-humble-run-hiwin-moveit
             | ros-humble-run-hiwin-plc
             | ros-humble-rrbot-bringup
             | ros-humble-rrbot-description
             | ros-humble-rrbot-hardware
             | ros-humble-rrbot-moveit-config
             | ros-humble-rrbot-moveit-demo
             | ros-humble-jaka-bringup
             | ros-humble-jaka-description
             | ros-humble-jaka-hardware
             | ros-humble-jaka-moveit-config
             | ros-humble-jaka-moveit-py
             | ros-humble-run-jaka-moveit
             | ros-humble-run-jaka-plc
           - The Industrial Motion-Control ROS2 Gateway is the communication bridge between DDS/RSTP wire-protocol ROS2 implementation and Motion Control (MC) IEC-61131-3 standard Intel implementation
         * - :doc:`VSLAM: ORB-SLAM3 <sample_pipelines/ORB_VSLAM>`
           - | libpangolin
             | liborb-slam3
             | liborb-slam3-dev
             | orb-slam3
           - Visual SLAM demo pipeline based on ORB-SLAM3. Refer to :doc:`VSLAM: ORB-SLAM3 <sample_pipelines/ORB_VSLAM>` for installation and launching tutorials.
         * - `RealSense Camera <https://wiki.ros.org/RealSense>`__
           - | librealsense2
             | librealsense2-dev
             | librealsense2-utils
             | librealsense2-udev-rules
             | ros-humble-librealsense2
             | ros-humble-librealsense2-tools
             | ros-humble-librealsense2-udev
             | ros-humble-realsense2-camera
             | ros-humble-realsense2-camera-msgs
             | ros-humble-realsense2-description
           - RealSense Camera driver and tools.
         * - :doc:`Imitation Learning - ACT <sample_pipelines/imitation_learning_act>`
           - | act-ipex
             | act-ov
           - Action Chunking with Transformers (ACT), a method that trains a generative model to understand and predict action sequences.


.. toctree::
   :maxdepth: 1
   :hidden:

   packages/linuxbsp
   packages/ethercat
   packages/mc_gateway
   
