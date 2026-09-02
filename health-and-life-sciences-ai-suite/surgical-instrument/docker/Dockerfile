# Updated Endoscopy Demo — standalone image.
#
# Based on the SAME DL Streamer / OpenVINO 2026.1 base that the existing
# `surgical-pipeline` container uses, because its GPU runtime is already proven
# to run OpenVINO GPU inference on the target hardware (ARL/PTL). Building our
# own GPU stack on plain Ubuntu mismatched the driver and crashed
# `compile_model("GPU")` — so we reuse the known-good base and only add OpenCV.
#
# This image already ships: Python 3, OpenVINO 2026.x (+ GPU plugin & drivers),
# numpy, and pypylon. We add OpenCV (with X11 display libs) on top.
#
# Runtime needs (see Makefile): /dev/dri passthrough, X11 socket for display,
# and (for Basler) /dev/bus/usb + the USB cgroup rule.
 
FROM intel/dlstreamer-pipeline-server:2026.1.0-ubuntu24
 
# Optional corporate proxy (leave empty for none).
ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG NO_PROXY=
ENV HTTP_PROXY=${HTTP_PROXY} HTTPS_PROXY=${HTTPS_PROXY} NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} https_proxy=${HTTPS_PROXY} no_proxy=${NO_PROXY} \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
 
USER root
 
# OpenCV runtime libs (libgl/glib for cv2 + its window, libusb for pypylon).
# Do NOT reinstall openvino/numpy — they come from the base image and must not
# be overridden (that version mismatch is what broke the GPU path).
#
# Strip the base image's Intel apt source first: it points at apt.repos.intel.com,
# which our proxy can't reach (NO_PROXY covers .intel.com -> direct connect times
# out). We only pull these libs from Ubuntu's repos, so dropping it is safe.
RUN find /etc/apt -name '*.list' -o -name '*.sources' | xargs -r grep -lE 'intel\.com' 2>/dev/null | xargs -r rm -f \
    && apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libusb-1.0-0 libsm6 libice6 \
        libglfw3 libglx-mesa0 libgl1-mesa-dri libopengl0 libglx0 libglvnd0 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir opencv-python glfw PyOpenGL
 
# pypylon usually ships in the base image; install only if missing.
RUN python3 -c "import pypylon" 2>/dev/null || pip install --no-cache-dir pypylon
 
# --- App ---------------------------------------------------------------------
WORKDIR /app
COPY src/app.py src/detector.py src/sources.py src/config.py src/display.py src/vsync.py /app/
 
# Sensible container defaults; override with `docker run -e ...` or Makefile.
ENV MODEL=/models/yolo11n_polyp/best_openvino_model/best.xml \
    DEVICE=GPU \
    SOURCE=file \
    SOURCE_ARG=/videos/polyp_test.mp4
 
ENTRYPOINT ["python3", "app.py"]
 