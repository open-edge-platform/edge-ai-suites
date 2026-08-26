# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Surgical Instrument — DL Streamer pipeline container.
#
# Base: Intel DL Streamer Pipeline Server 2026.1.0 (contains gstreamer 1.28,
# gva* plugins, VA-API, OpenVINO 2026, and the latency_tracer plugin).
#
# We add a thin Flask control plane on :8000 that spawns `gst-launch-1.0` as
# a subprocess with the finalized file/Basler pipeline strings, opens the
# annotated video in a host X11 popup, and parses the latency_tracer stderr
# into rolling P50/P90/P95/P99 percentiles served over HTTP.

FROM intel/dlstreamer-pipeline-server:2026.1.0-ubuntu24


USER root

# Flask for the control plane HTTP API. pypylon remains available for local
# Basler serial enumeration, while pylon SDK + gencamsrc provide the live
# GStreamer camera source used by the runtime pipeline.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      cmake \
      g++ \
      git \
      gnupg \
      gstreamer1.0-plugins-base \
      libgstreamer-plugins-base1.0-dev \
      libgstreamer1.0-dev \
      libusb-1.0-0 \
      libxcb-cursor0 \
      wget \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir --retries 4 --timeout 60 \
      flask==3.0.3 \
      pypylon==4.0.0

RUN cd /tmp \
 && wget -q https://downloads-ctf.baslerweb.com/dg51pdwahxgw/16EbjATpV78LtOFUQ1VpJM/ab3db40227afb59df3eb1cccf0c5addc/pylon-7.5.0.15658-linux-x86_64_debs.tar.gz \
 && tar -xzf pylon-7.5.0.15658-linux-x86_64_debs.tar.gz \
 && rm pylon-7.5.0.15658-linux-x86_64_debs.tar.gz \
 && dpkg -i pylon_7.5.0.15658-deb0_amd64.deb || apt-get update && apt-get install -fy \
 && rm -f /tmp/pylon_7.5.0.15658-deb0_amd64.deb \
 && rm -rf /var/lib/apt/lists/*

RUN cd /tmp \
 && wget -q https://github.com/basler/gst-plugin-pylon/releases/download/v1.0.0/gst-plugin-pylon_1.0.0-1.ubuntu-24.04_amd64.deb \
 && dpkg -i gst-plugin-pylon_1.0.0-1.ubuntu-24.04_amd64.deb || apt-get update && apt-get install -fy \
 && rm -f /tmp/gst-plugin-pylon_1.0.0-1.ubuntu-24.04_amd64.deb \
 && rm -rf /var/lib/apt/lists/*



# gencamsrc fix — overwrite upstream plugins/genicam.{h,cc} before building
COPY genicam.h  /tmp/gencamsrc-fix/genicam.h
COPY genicam.cc /tmp/gencamsrc-fix/genicam.cc

RUN git clone --depth 1 --branch release-2026.1.0 https://github.com/open-edge-platform/edge-ai-libraries.git /tmp/edge-ai-libraries \
 && cp -r /tmp/edge-ai-libraries/microservices/dlstreamer-pipeline-server/plugins/camera/src-gst-gencamsrc /home/pipeline-server/src-gst-gencamsrc \
 && cp /tmp/gencamsrc-fix/genicam.h  /home/pipeline-server/src-gst-gencamsrc/plugins/genicam.h \
 && cp /tmp/gencamsrc-fix/genicam.cc /home/pipeline-server/src-gst-gencamsrc/plugins/genicam.cc \
 && cd /home/pipeline-server/src-gst-gencamsrc \
 && cmake -B build -DCMAKE_BUILD_TYPE=Release \
 && cmake --build build -j$(nproc) \
 && cmake --install build \
 && ldconfig \
 && rm -rf /tmp/edge-ai-libraries /tmp/gencamsrc-fix

ENV GENICAM_GENTL64_PATH=/opt/pylon/lib/gentlproducer/gtl \
    GST_PLUGIN_PATH=/opt/intel/dlstreamer/lib:/opt/intel/dlstreamer/gstreamer/lib/gstreamer-1.0:/opt/intel/dlstreamer/gstreamer/lib/:/usr/lib/x86_64-linux-gnu/gstreamer-1.0:/usr/local/lib/gstreamer-1.0

COPY launcher.py            /opt/launcher.py
COPY pipeline_string.py     /opt/pipeline_string.py
COPY latency_tracer_sink.py /opt/latency_tracer_sink.py
COPY bbox_filter.py         /opt/bbox_filter.py
COPY watermark_green.py     /opt/watermark_green.py
COPY basler_reader.py       /opt/basler_reader.py

ENV PIPELINE_HTTP_PORT=8000

EXPOSE 8000

ENTRYPOINT ["python3", "/opt/launcher.py"]