# Surgical Instrument — DL Streamer pipeline container.
#
# Base: Intel DL Streamer Pipeline Server 2026.1.0 (contains gstreamer 1.28,
# gva* plugins, VA-API, OpenVINO 2026, and the latency_tracer plugin).
#
# We add a thin Flask control plane on :8000 that spawns `gst-launch-1.0` as
# a subprocess with the polyp-detection pipeline string and captures the
# canonical latency_tracer output to /frames/latency.log.

FROM intel/dlstreamer-pipeline-server:2026.1.0-ubuntu24-rc1.1

USER root

# Flask for the control plane; paho-mqtt for the in-pipeline gvapython
# publisher (see mqtt_publisher.py for the rationale).
RUN pip install --no-cache-dir flask==3.0.3 paho-mqtt==1.6.1

COPY launcher.py         /opt/launcher.py
COPY pipeline_string.py  /opt/pipeline_string.py
COPY mqtt_publisher.py   /opt/mqtt_publisher.py
COPY bbox_filter.py      /opt/bbox_filter.py
COPY watermark_green.py  /opt/watermark_green.py

ENV PIPELINE_HTTP_PORT=8000 \
    FRAME_DIR=/frames

EXPOSE 8000

ENTRYPOINT ["python3", "/opt/launcher.py"]
