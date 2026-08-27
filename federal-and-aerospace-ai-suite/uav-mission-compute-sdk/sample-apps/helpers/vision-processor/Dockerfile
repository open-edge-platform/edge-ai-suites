# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM intel/dlstreamer:2026.1.0-ubuntu24

USER root

ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}

WORKDIR /app

RUN pip install --no-cache-dir --break-system-packages --ignore-installed numpy paho-mqtt opencv-python-headless

# Download Intel YOLO vehicle detection model (better for aerial/top-down views)
# yolo-v2-tiny-vehicle-detection-0001: COCO-trained, handles various perspectives
RUN mkdir -p /models/intel/yolo-v2-tiny-vehicle-detection-0001/FP16 && \
    curl -sL https://storage.openvinotoolkit.org/repositories/open_model_zoo/2022.1/models_bin/3/yolo-v2-tiny-vehicle-detection-0001/FP16/yolo-v2-tiny-vehicle-detection-0001.xml \
    -o /models/intel/yolo-v2-tiny-vehicle-detection-0001/FP16/yolo-v2-tiny-vehicle-detection-0001.xml && \
    curl -sL https://storage.openvinotoolkit.org/repositories/open_model_zoo/2022.1/models_bin/3/yolo-v2-tiny-vehicle-detection-0001/FP16/yolo-v2-tiny-vehicle-detection-0001.bin \
    -o /models/intel/yolo-v2-tiny-vehicle-detection-0001/FP16/yolo-v2-tiny-vehicle-detection-0001.bin

ENV HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy=""

COPY detector_multicam.py .
COPY detector_multicam_rtsp.py .
COPY entrypoint.sh .
COPY yolov8.json /models/
RUN chmod +x entrypoint.sh

# Restore DL Streamer environment
ENV GST_PLUGIN_PATH=/opt/intel/dlstreamer/lib:/opt/intel/dlstreamer/gstreamer/lib/gstreamer-1.0:/opt/intel/dlstreamer/gstreamer/lib/
ENV LD_LIBRARY_PATH=/opt/intel/dlstreamer/gstreamer/lib:/opt/intel/dlstreamer/lib:/opt/intel/dlstreamer/lib/gstreamer-1.0:/opt/opencv:/opt/rdkafka:/opt/librealsense:/usr/local/lib/gstreamer-1.0:/usr/local/lib
ENV GI_TYPELIB_PATH=/opt/intel/dlstreamer/gstreamer/lib/girepository-1.0:/opt/intel/dlstreamer/lib/girepository-1.0:/usr/lib/x86_64-linux-gnu/girepository-1.0
ENV PYTHONPATH=/opt/intel/dlstreamer/gstreamer/lib/python3/dist-packages:/opt/intel/dlstreamer/python
ENV GST_VA_ALL_DRIVERS=1
ENV LIBVA_DRIVERS_PATH=/usr/lib/x86_64-linux-gnu/dri

USER dlstreamer

CMD ["/app/entrypoint.sh"]
