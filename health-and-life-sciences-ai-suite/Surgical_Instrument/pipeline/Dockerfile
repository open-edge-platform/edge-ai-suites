# Surgical Instrument — DL Streamer pipeline container.
#
# Base: Intel DL Streamer Pipeline Server 2026.1.0 (contains gstreamer 1.28,
# gva* plugins, VA-API, OpenVINO 2026, and the latency_tracer plugin).
#
# We add a thin Flask control plane on :8000 that spawns `gst-launch-1.0` as
# a subprocess with the polyp-detection pipeline string and captures the
# canonical latency_tracer output to /frames/latency.log.

FROM intel/dlstreamer-pipeline-server:2026.1.0-ubuntu24-rc1.1

# Proxy support for corporate networks. Build args are optional; if not
# supplied, defaults to empty (no proxy). Pass via docker build --build-arg
# or docker-compose build args.
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY}

USER root

# Flask for the control plane; paho-mqtt for the in-pipeline gvapython
# publisher (see mqtt_publisher.py for the rationale). pypylon + libusb
# are the runtime deps for Slice E-b (Basler streaming via basler_reader.py
# → fdsrc bridge). Kept as a single install layer so image size stays
# predictable and the layer only invalidates when we bump a dep.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libusb-1.0-0 \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir --retries 4 --timeout 60 \
      flask==3.0.3 \
      paho-mqtt==1.6.1 \
      pypylon==4.0.0

COPY launcher.py         /opt/launcher.py
COPY pipeline_string.py  /opt/pipeline_string.py
COPY mqtt_publisher.py   /opt/mqtt_publisher.py
COPY bbox_filter.py      /opt/bbox_filter.py
COPY watermark_green.py  /opt/watermark_green.py
COPY basler_reader.py    /opt/basler_reader.py

ENV PIPELINE_HTTP_PORT=8000 \
    FRAME_DIR=/frames

EXPOSE 8000

ENTRYPOINT ["python3", "/opt/launcher.py"]
