# syntax=docker/dockerfile:1
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM ubuntu:24.04

ARG http_proxy
ARG https_proxy
ARG no_proxy
ENV http_proxy=${http_proxy} \
    https_proxy=${https_proxy} \
    no_proxy=${no_proxy} \
    DEBIAN_FRONTEND=noninteractive

RUN if [ -n "${http_proxy}" ]; then \
      echo "Acquire::http::Proxy \"${http_proxy}\";"   > /etc/apt/apt.conf.d/00proxy; \
      echo "Acquire::https::Proxy \"${https_proxy}\";" >> /etc/apt/apt.conf.d/00proxy; \
      echo "http_proxy=${http_proxy}"   >> /etc/environment; \
      echo "https_proxy=${https_proxy}" >> /etc/environment; \
      echo "no_proxy=${no_proxy}"       >> /etc/environment; \
    fi

# Ensure video and render groups exist for GPU device access
RUN groupadd -f render && groupadd -f video

# Intel GPU stack (Mesa + iris driver for integrated Intel GPUs)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      wget gpg ca-certificates \
    && if [ -n "${https_proxy}" ]; then \
         echo "https_proxy=${https_proxy}" >> /etc/wgetrc; \
         echo "http_proxy=${http_proxy}"   >> /etc/wgetrc; \
         echo "use_proxy=on"               >> /etc/wgetrc; \
       fi \
    && wget -qO - https://repositories.intel.com/gpu/intel-graphics.key \
       | gpg --dearmor -o /usr/share/keyrings/intel-graphics.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] \
       https://repositories.intel.com/gpu/ubuntu noble unified" \
       > /etc/apt/sources.list.d/intel-gpu.list \
    && apt-get update && apt-get install -y --no-install-recommends \
       libgl1-mesa-dri \
       libglx-mesa0 \
       libegl-mesa0 \
       mesa-vulkan-drivers \
       libgbm1 \
       libxatracker2 \
       libigdgmm12

# PX4 build toolchain via PX4's own ubuntu.sh
ARG PX4_VERSION=v1.17.0
ARG http_proxy
ARG https_proxy
ARG no_proxy
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      git curl sudo lsb-release \
    && if [ -n "${http_proxy}" ]; then \
         git config --system http.proxy  "${http_proxy}"; \
         git config --system https.proxy "${https_proxy}"; \
       fi

# PX4 version is pinned for deterministic builds.
RUN echo "Using pinned PX4 version: ${PX4_VERSION}"

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
  git clone --depth 1 --branch "${PX4_VERSION}" \
         https://github.com/PX4/PX4-Autopilot.git /tmp/px4-setup \
    && bash /tmp/px4-setup/Tools/setup/ubuntu.sh --no-nuttx \
    && rm -rf /tmp/px4-setup

# Gazebo Harmonic
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
       libgz-sim8-dev \
       libgz-transport13-dev \
       libgz-sensors8-dev \
       gz-harmonic

# Pre-download Gazebo Fuel models used by baylands_detection world.
# Baking them into the image avoids any runtime downloads — works offline,
# behind strict proxies, and starts instantly on every container run.
ARG http_proxy
ARG https_proxy
ARG no_proxy
RUN gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/baylands" \
    && gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Coast Water" \
    && gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Hatchback" \
    && gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Hatchback red" \
    && gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/SUV" \
    && gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Pickup" \
    && gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Construction Cone" \
    && gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Construction Barrel" \
    && gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Rescue Randy"

# PX4 source + submodules — uses pinned PX4 version
ARG http_proxy
ARG https_proxy
ARG no_proxy
RUN git clone --depth 1 --branch "${PX4_VERSION}" \
      https://github.com/PX4/PX4-Autopilot.git /px4 \
    && cd /px4 \
    && git submodule update --init --recursive --depth 1 --jobs "$(nproc)"

# Compile SITL binaries
RUN cd /px4 && make px4_sitl_default

# PX4 parameters — appended directly to the airframe init script so they run
# after all param set-default calls and override them unconditionally.
# start_px4.sh wipes parameters.bson before each boot so these always apply fresh.
RUN AIRFRAME=/px4/ROMFS/px4fmu_common/init.d-posix/airframes/4014_gz_x500_mono_cam_down \
    && echo ''                             >> $AIRFRAME \
    && echo '# POC overrides'             >> $AIRFRAME \
    && echo 'param set SDLOG_MODE -1'      >> $AIRFRAME \
    && echo 'param set COM_DISARM_LAND 5'  >> $AIRFRAME \
    && echo 'param set MIS_TAKEOFF_ALT 5'  >> $AIRFRAME \
    && echo 'param set RTL_RETURN_ALT 10'  >> $AIRFRAME \
    && echo 'param set RTL_DESCEND_ALT 5'  >> $AIRFRAME \
    && echo 'param set RTL_LAND_DELAY 0'   >> $AIRFRAME \
    && echo 'param set MAV_1_BROADCAST 1'  >> $AIRFRAME \
    && echo 'param set COM_RCL_EXCEPT 4'  >> $AIRFRAME

COPY start_px4.sh /root/start_px4.sh
RUN chmod +x /root/start_px4.sh

# Bake custom world and camera model into the image so remote deploys work
# without needing volume mounts from the host.
COPY worlds/baylands_detection.sdf /px4/Tools/simulation/gz/worlds/baylands_detection.sdf
COPY models/mono_cam/model.sdf     /px4/Tools/simulation/gz/models/mono_cam/model.sdf

# Clear proxy for runtime
ENV http_proxy= \
    https_proxy= \
    no_proxy=

ENV HEADLESS=1
WORKDIR /px4
CMD ["/root/start_px4.sh"]
