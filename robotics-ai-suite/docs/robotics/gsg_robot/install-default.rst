#. Choose the |amr_package_name| |deb_pack| to install.

   **ros-humble-robotics-sdk**
      The standard version of the |p_amr|. This package includes almost everything except for a handful of tutorials and bag files.

   **ros-humble-robotics-sdk-complete**
      The complete version of the |p_amr|. It also includes those items excluded from the standard version. Please note that the complete SDK downloads approximately 20GB of additional files.

#. Install the chosen |amr_package_name| |deb_pack|

   .. note::

      Before you install ros-humble-robotics-sdk-complete (or any other packages that depend on OpenVINO), please read the information on :doc:`install-openvino`.
 
   Install command example:

   .. code-block:: bash

      sudo apt install ros-humble-robotics-sdk

   The standard version of the |amr_package_name| should generally download and install
   all files within just a few minutes. The complete version of the |amr_package_name| will take
   several more minutes and consume significantly more network bandwidth.

   The actual installation time will vary greatly based primarily upon the number of packages that
   need to be installed and the network connection speed.

   .. figure:: ../images/download/apt-install-ros-pkt.png
