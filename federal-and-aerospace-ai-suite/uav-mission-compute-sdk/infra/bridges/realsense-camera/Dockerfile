# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM ubuntu:24.04

ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV HTTP_PROXY=${HTTP_PROXY} HTTPS_PROXY=${HTTPS_PROXY} DEBIAN_FRONTEND=noninteractive

# ffmpeg (RTSP encode) + libusb (USB transport used by the pyrealsense2 wheel)
RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    ffmpeg \
    libusb-1.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed -r requirements.txt

ENV HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy=""

COPY realsense_camera_bridge.py .

CMD ["python3", "-u", "realsense_camera_bridge.py"]
