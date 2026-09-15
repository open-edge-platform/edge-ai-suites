# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM ubuntu:24.04

ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV HTTP_PROXY=${HTTP_PROXY} HTTPS_PROXY=${HTTPS_PROXY} DEBIAN_FRONTEND=noninteractive

# GStreamer (v4l2src capture) + ffmpeg (RTSP encode) + v4l-utils (device enumeration)
RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    ffmpeg \
    v4l-utils \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    python3-gi \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed -r requirements.txt

ENV HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy=""

COPY usb_camera_bridge.py .

CMD ["python3", "-u", "usb_camera_bridge.py"]
