
#. Before using the |amr_package_name| APT repositories, update the APT packages list:

   .. code-block:: bash

      sudo apt update

   The APT package manager will download the latest list of packages available for all configured repositories.

      .. figure:: ../images/download/apt-update.png

   .. note::

      If the APT package manager is unable to connect to the repositories, follow these APT troubleshooting tips:

      * Make sure that the system has network connectivity.
      * Make sure that port 80 is not blocked by a firewall.
      * Configure an APT proxy (if network traffic routes through a proxy server).

         To configure an APT proxy, add the following lines to a file at
         `/etc/apt/apt.conf.d/proxy.conf` (replace the placeholder as per your specific user and proxy server)::

            Acquire:http:Proxy "http://user:password@proxy.server:port/";
            Acquire:https:Proxy "http://user:password@proxy.server:port/";

         To ensure proper proxy settings for other tools required during the package installation
         add the the required proxy settings to `/etc/environment`::

            http_proxy=http://user:password@proxy.server:port
            https_proxy=http://user:password@proxy.server:port
            no_proxy="localhost,127.0.0.1,127.0.0.0/8"

         After setting the proxy values in `/etc/apt/apt.conf.d/proxy.conf` and `/etc/environment`
         you will have to reboot the device, so these settings become effective.

   
#. Choose the |amr_package_name| |deb_pack| to install.

   **ros-humble-aaeon-adbscan-tutorial**
      AAEON Robot ADBSCAN mapping with FastMapping algorithm using |realsense| camera.

   **ros-humble-aaeon-ros2-amr-interface**
      Lightweight package to get AMRs working with |ros|.

   **ros-humble-adbscan-ros2**
      Adaptive Density-based Spatial Clustering of Applications with Noise (ADBSCAN) for |ros|.

   **ros-humble-adbscan-ros2-follow-me**
      Enable a robot to follow a specific person or target based on Adaptive DBScan clustering and gesture based motion control.

   **ros-humble-collab-slam-avx2**
      Collaborative SLAM for AVX2 CPU instruction accelerated package on supported Intel Core processors

   **ros-humble-collab-slam-lze**
      Collaborative SLAM for GPU Level-Zero accelerated package on supported Intel processors with integrated graphics

   **ros-humble-collab-slam-sse**
      Collaborative SLAM for SSE-only CPU instruction accelerated package on supported Intel Atom processors

   **ros-humble-cslam-tutorial-all**
      Collaborative SLAM all tutorials.

   **ros-humble-fast-mapping**
      Allen Fast Mapping, a |ros| package for real-time scene modeling from sequential depth images from prerecorded |ros| bag.

   **ros-humble-follow-me-tutorial**
      Follow-Me application with ADBSCAN using |realsense| camera.

   **ros-humble-followme-turtlebot3-gazebo**
      An adaptation of |tb3| simulation by Intel to include a multi robot environment to demo the follow me algorithm.

   **ros-humble-its-planner**
      Intelligent Sampling and Two-Way Search.

   **ros-humble-its-relocalization-bringup**
      Re-localization bring up package.

   **ros-humble-picknplace-simulation**
      Meta Package for pick n place simulation deb files.

   **ros-humble-realsense2-tutorial-demo**
      |realsense| tutorial with sample application.

   **ros-humble-wandering**
      Wandering application.

   **ros-humble-wandering-tutorials**
      Meta-package for |intel| Wandering application tutorials.

   .. raw:: html

      <br/>

#. Install the chosen |amr_package_name| |deb_pack|.

   .. note::

      Before you install ros-humble-robotics-sdk-complete (or any other packages that depend on OpenVINO), please read the information on :doc:`install-openvino`.

   Install command example:

   .. code-block:: bash

      sudo apt install <package-name>
