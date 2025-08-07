To run |lp_amr| in a |Docker| container you must have Docker installed on your system.
You can go with an existing installation or start with a fresh install.

**Install Docker**

  Follow the `Install Docker_Engine on Ubuntu OS <https://docs.docker.com/engine/install/ubuntu/>`__ guide, to install |Docker| on your target system.

  After `uninstalling any old Docker Engine versions <Uninstall old versions>`__
  you have the option to:

   * `Install using the Apt repository <https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository>`__

   * `Install from a Deb package file <https://docs.docker.com/engine/install/ubuntu/#install-from-a-package>`__

   * `Install using the convenience script <https://docs.docker.com/engine/install/ubuntu/#install-using-the-convenience-script>`__

  Now you are ready to set up a Dockerfile that you can use to create your own |lp_amr| |Docker| image.

  Follow the `Dockerfile reference <https://docs.docker.com/engine/reference/builder/>`__ to learn how to create and launch your Docker image.

**Example of installing the Robotics SDK inside a |Docker| container**

   .. note::

      | The following example is provided as a reference only.
      | Modify for your specific needs and environment, include for instance any proxy settings that may be necessary.

  * Sample Dockerfile

    The Dockerfile defines the content of your Docker image.

    .. code-block:: bash

      # Create image from ROS2 Humble base
      FROM ros:humble-ros-base-jammy

      ENV DEBIAN_FRONTEND=noninteractive

      # Install bootstrap packages
      RUN apt-get update \
         && apt-get install --no-install-recommends -y git apt-utils wget \
         && rm -rf /var/lib/apt/lists/*

      # Add APT gpg key
      RUN bash -c 'wget -q -O- https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg | tee /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null'

      # Add ECI APT repo
      RUN bash -c 'echo "deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(lsb_release -sc) isar main" | tee /etc/apt/sources.list.d/eci.list'
      RUN bash -c 'echo "deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(lsb_release -sc) isar main" | tee -a /etc/apt/sources.list.d/eci.list'
      RUN bash -c 'echo -e "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" | tee /etc/apt/preferences.d/isar'

      # Add AMR APT repo
      RUN bash -c 'echo "deb [trusted=yes] https://amrdocs.intel.com/repos/$(lsb_release -sc) amr main" | tee /etc/apt/sources.list.d/amr.list'
      RUN bash -c 'echo "deb-src [trusted=yes] https://amrdocs.intel.com/repos/$(lsb_release -sc) amr main" | tee -a /etc/apt/sources.list.d/amr.list'
      RUN bash -c 'echo -e "Package: *\nPin: origin amrdocs.intel.com\nPin-Priority: 1001" | tee /etc/apt/preferences.d/isar'

      # Add oneAPI APT repo
      RUN bash -c 'wget -q -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | tee /usr/share/keyrings/oneapi-archive-keyring.gpg'
      RUN bash -c 'echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneAPI.list'
      RUN bash -c 'echo -e "Package: intel-oneapi-runtime-*\nPin: version 2024.1.*\nPin-Priority: 1001" > /etc/apt/preferences.d/oneAPI'

      # Add RealSense APT repo
      RUN bash -c 'mkdir -p /root/.gnupg'
      RUN bash -c 'gpg --no-default-keyring --keyring /usr/share/keyrings/realsense-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys F6E65AC044F831AC80A06380C8B3A55A6F3EFCDE'
      RUN bash -c 'echo "deb [signed-by=/usr/share/keyrings/realsense-archive-keyring.gpg] https://librealsense.intel.com/Debian/apt-repo $(lsb_release -sc) main" | tee /etc/apt/sources.list.d/realsense2.list'

      # Add OpenVINO APT repo
      RUN bash -c 'wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | sudo tee /usr/share/keyrings/openvino-archive-keyring.gpg'
      RUN bash -c 'echo "deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino/2023 ubuntu22 main" | sudo tee /etc/apt/sources.list.d/intel-openvino-2023.list'
      RUN bash -c 'echo "deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino/2024 ubuntu22 main" | sudo tee /etc/apt/sources.list.d/intel-openvino-2024.list'

      RUN bash -c 'echo -e "\nPackage: openvino-libraries-dev\nPin: version 2024.2.0*\nPin-Priority: 1001" | sudo tee /etc/apt/preferences.d/intel-openvino'
      RUN bash -c 'echo -e "\nPackage: openvino\nPin: version 2024.2.0*\nPin-Priority: 1001" | sudo tee -a /etc/apt/preferences.d/intel-openvino'
      RUN bash -c 'echo -e "\nPackage: ros-humble-openvino-wrapper-lib\nPin: version 2024.2.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino'
      RUN bash -c 'echo -e "\nPackage: ros-humble-openvino-node\nPin: version 2024.2.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino'

      # Ignore flann version 1.19
      RUN bash -c 'echo -e "\nPackage: libflann*\nPin: version 1.19.*\nPin-Priority: -1\n\nPackage: flann*\nPin: version 1.19.*\nPin-Priority: -1" >> /etc/apt/preferences.d/isar'

      # Populate debconf database with GPU selection for liborb-lze to eliminate the need for prompt
      ARG GPU_GEN=gen12lp
      RUN echo "liborb-lze liborb-lze/march select ${GPU_GEN}" | debconf-set-selections
      RUN echo "liborb-lze:amd64 liborb-lze/march select ${GPU_GEN}" | debconf-set-selections

      # Install robotics-sdk package
      RUN apt-get update \
         && apt-get install -y ros-humble-robotics-sdk \
         && rm -rf /var/lib/apt/lists/*

      # Add render group as necessary
      ARG RENDER_ID=109
      RUN if [ $(getent group render) ] ; then echo 'exists' ; else groupadd --gid ${RENDER_ID} render ; fi

      # Config environ
      ARG DOCKER_USER=amr
      ARG DOCKER_USER_UID=1000
      ARG DOCKER_USER_GROUPS=sudo,video,audio,plugdev,dialout,render

      ENV DOCKER_USER         ${DOCKER_USER}
      ENV DOCKER_USER_UID     ${DOCKER_USER_UID}
      ENV HOME_DOCKER_USER    /home/${DOCKER_USER}
      ENV WORKSPACE_DIR       ${HOME_DOCKER_USER}/workspace

      # Create User
      SHELL ["/bin/bash", "-xo", "pipefail", "-c"]
      USER root
      RUN useradd --create-home --shell /bin/bash --gid root --uid ${DOCKER_USER_UID} --groups ${DOCKER_USER_GROUPS} ${DOCKER_USER} \
         && passwd -d root \
         && passwd -d ${DOCKER_USER} \
         && echo "${DOCKER_USER} ALL=(ALL) NOPASSWD:ALL" | tee /etc/sudoers.d/${DOCKER_USER} \
         && echo 'export DISPLAY=":1"' >> /home/${DOCKER_USER}/.bashrc \
         && echo 'source /opt/ros/humble/setup.bash' >> /home/${DOCKER_USER}/.bashrc

      # Create workspace folder
      RUN mkdir -p ${WORKSPACE_DIR} && chown ${DOCKER_USER}:${DOCKER_USER_UID} ${WORKSPACE_DIR}
      WORKDIR ${WORKSPACE_DIR}

      USER ${DOCKER_USER}

      CMD ["/bin/bash"]

  * Sample create script

    Run the create script to create your |Docker| image based on the Dockerfile.

    .. code-block:: bash

      #!/bin/bash
      cd "$( dirname "$0" )"

      sudo apt install -y intel-gpu-tools debconf-utils

      echo -e ""
      sudo intel_gpu_top -L

      echo -e "\nSelect the Intel integrated GPU present on this system. Suggested value is shown in the output above."
      echo "  1. gen9  2. gen11  3. gen12lp"

      while :; do
         read -p "Select GPU Generation (1, 2, or 3): " NBR
         [[ $NBR =~ ^[0-9]+$ ]] || { continue; }
         if ((NBR >= 1 && NBR <= 3)); then
            if [ $NBR = "1" ]; then
                  GPU_GEN=gen9
            fi
            if [ $NBR = "2" ]; then
                  GPU_GEN=gen11
            fi
            if [ $NBR = "3" ]; then
                  GPU_GEN=gen12lp
            fi
            break
         fi
      done

      docker rmi robotics-sdk:latest 2>/dev/null
      docker build --no-cache --build-arg="GPU_GEN=$GPU_GEN" --build-arg="RENDER_ID=$(getent group render | cut -d: -f3)" -f Dockerfile -t robotics-sdk .

  * Sample launch script

    Launches the |Docker| image in |Docker| container.

    .. code-block:: bash

      #!/bin/bash
      cd "$( dirname "$0" )"

      docker run -it --rm -v /dev:/dev:ro --name robotics-sdk --network=host --privileged robotics-sdk:latest
