# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Surgical Instrument — backend image.
#
# Runs the Phase 3 Flask server (backend.main_server) with a first-boot
# bootstrap that fetches ColonDB (manual-drop), trains YOLO11n on the
# host's Intel Arc / Xe iGPU via torch+xpu, and exports to OpenVINO IR.
#
# The host mounts /dev/dri (and /dev/accel for NPU, optional). The container
# needs the Intel graphics compute runtime (Level Zero GPU/NPU drivers +
# OpenCL ICD) — installed from Intel's official Ubuntu 24.04 repo. Without
# these, torch.xpu.device_count() returns 0 even when /dev/dri is mounted
# and the process is in the render group.

# ==========================================================================
# Stage 1 (builder): install every Python package, then hand only the
# resulting /usr/local tree to the runtime stage. Build-only tooling
# (compilers, dev headers, pip caches) and the transient CUDA payload
# Ultralytics pulls never reach the final image.
# ==========================================================================
FROM ubuntu:24.04 AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 \
      python3-pip \
      python3-dev \
      build-essential \
      wget \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Intel oneAPI Python runtime that torch+xpu links against at run time
# (SYCL, oneMKL, TBB, OpenMP, compiler runtimes). torch itself is installed
# in a single later layer (with the app requirements) so the ~2 GB wheel is
# not duplicated across layers and the transient CUDA payload Ultralytics
# pulls can be purged in that same layer.
#
# Version pin matches the poc/gabriel_test/.venv setup that trained YOLO11n
# on MTL's Arc iGPU end-to-end in ~21 minutes for 50 epochs. torch 2.7.x
# had immature SYCL kernels for YOLO's loss / target-assignment ops and
# stalls indefinitely inside get_assigned_targets_and_loss on Xe3.
RUN pip install \
      --retries 8 \
      --timeout 120 \
      "filelock>=3.13" \
      "typing-extensions>=4.10" \
      "sympy>=1.13.3" \
      "networkx>=3.0" \
      "jinja2>=3.1" \
      "fsspec>=2024.2.0" \
      "pyyaml>=6.0" \
      "intel-pti==0.16.0" \
      "intel-cmplr-lib-rt==2025.3.2" \
      "intel-cmplr-lib-ur==2025.3.2" \
      "intel-cmplr-lic-rt==2025.3.2" \
      "intel-sycl-rt==2025.3.2" \
      "intel-opencl-rt==2025.3.2" \
      "intel-openmp==2025.3.2" \
      "dpcpp-cpp-rt==2025.3.2" \
      "mkl==2025.3.1" \
      "onemkl-license==2025.3.1" \
      "onemkl-sycl-blas==2025.3.1" \
      "onemkl-sycl-dft==2025.3.1" \
      "onemkl-sycl-lapack==2025.3.1" \
      "onemkl-sycl-rng==2025.3.1" \
      "onemkl-sycl-sparse==2025.3.1" \
      "tbb==2022.3.1" \
      "tcmlib==1.4.1" \
      "umf==1.0.3" \
      "oneccl==2021.17.2" \
      "impi-rt==2021.17.2"

COPY backend/requirements.txt /tmp/requirements.txt
# Single layer: install the app requirements (Ultralytics transiently pulls a
# CUDA torch build + multi-GB nvidia-* CUDA wheels), force the XPU torch/vision
# wheels back by direct URL (--no-deps so nothing else is touched), then purge
# the now-unused CUDA/triton payload. Doing all of this in one RUN means none
# of the transient CUDA download persists in an intermediate image layer.
#
# Direct download.pytorch.org URLs are used (not --index-url) because pip's
# index resolution redirects wheels through the Cloudflare R2 mirror whose TLS
# handshake is rejected by our corporate proxy; the primary S3 host works.
RUN pip install -r /tmp/requirements.txt \
 && pip install --retries 8 --timeout 120 --no-deps --force-reinstall \
      "https://download.pytorch.org/whl/xpu/torch-2.12.1%2Bxpu-cp312-cp312-linux_x86_64.whl" \
      "https://download.pytorch.org/whl/xpu/torchvision-0.27.1%2Bxpu-cp312-cp312-manylinux_2_28_x86_64.whl" \
 && pip freeze | grep -iE "^nvidia-|^triton" | cut -d'=' -f1 | xargs -r pip uninstall -y

# Ultralytics transitive resolution can pull CUDA/NVIDIA Python packages.
# Remove them so the final runtime image stays Intel XPU-only.
RUN python3 - <<'PY'
import importlib.metadata as md
import subprocess
import sys

installed = {dist.metadata.get("Name", "").strip() for dist in md.distributions()}
targets = sorted(
  n for n in installed if n and n.lower().startswith(("nvidia-", "cuda-"))
)

if targets:
  print("Removing CUDA/NVIDIA packages:", ", ".join(targets))
  subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", *targets])
else:
  print("No CUDA/NVIDIA Python packages found to remove")
PY

# Hard gate: fail build if any CUDA/NVIDIA package still remains.
RUN python3 - <<'PY'
import importlib.metadata as md

left = sorted(
  n
  for n in {dist.metadata.get("Name", "").strip() for dist in md.distributions()}
  if n and n.lower().startswith(("nvidia-", "cuda-"))
)

if left:
  raise SystemExit(f"ERROR: prohibited CUDA/NVIDIA packages still installed: {left}")
print("CUDA/NVIDIA Python package check passed")
PY

# Application code.
COPY backend/ /app/backend/

# ---------------------------------------------------------------------------
# Slice E: Basler USB3 camera enumeration. `pypylon` bundles the pylon USB3
# runtime (self-contained wheel); `libusb` is a runtime-only shared lib,
# installed via apt in the runtime stage below. Actual USB access is granted
# at `docker run` time via the /dev/bus/usb passthrough that `make up` wires
# in when it detects a Basler vendor ID 2676 on the host.
# ---------------------------------------------------------------------------
RUN pip install --retries 4 --timeout 60 pypylon==4.0.0


# ==========================================================================
# Stage 2 (runtime): fresh base + only the runtime apt libraries + the
# Python packages copied from the builder. No compilers, no pip build
# caches, no transient CUDA payload — just what the server needs to run.
# ==========================================================================
FROM ubuntu:24.04

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    DEBIAN_FRONTEND=noninteractive

# Runtime apt: Python, OpenCV/X shared libs, libusb (pylon), curl for the
# HEALTHCHECK, plus the Intel graphics compute runtime (Level Zero GPU +
# OpenCL ICD + media driver) that torch.xpu needs at run time. Without these
# torch.xpu.device_count() returns 0 even with /dev/dri mounted.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 \
      python3-pip \
      libglib2.0-0 \
      libgl1 \
      libsm6 \
      libxext6 \
      libxrender1 \
      libxcb1 \
      libusb-1.0-0 \
      curl \
      wget \
      gnupg \
      gpg-agent \
      ca-certificates \
    && wget -qO - https://repositories.intel.com/gpu/intel-graphics.key \
         | gpg --dearmor -o /usr/share/keyrings/intel-graphics.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu noble unified" \
         > /etc/apt/sources.list.d/intel-gpu-noble.list \
    && apt-get update && apt-get install -y --no-install-recommends \
      libze1 \
      libze-intel-gpu1 \
      intel-opencl-icd \
      intel-media-va-driver-non-free \
    && rm -rf /var/lib/apt/lists/*

# Bring over every Python package installed in the builder (torch+xpu, the
# Intel oneAPI runtime, ultralytics, pypylon, Flask, ...) plus console
# entry-point scripts and any bundled .so under /usr/local/lib. Both stages
# are ubuntu:24.04 -> Python 3.12, so the dist-packages path matches exactly.
COPY --from=builder /usr/local /usr/local

# Application code.
COPY backend/ /app/backend/

# Container-side paths. Override from compose to bind-mount host dirs.
ENV BACKEND_CONFIG=/app/backend/config/model.yaml \
    MODELS_DIR=/models \
    DATASETS_DIR=/datasets \
    VIDEOS_DIR=/videos \
    CACHE_DIR=/cache \
    HOST=0.0.0.0 \
    PORT=5001 \
    LD_LIBRARY_PATH=/usr/local/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH}

EXPOSE 5001

# First-boot may train for 20-35 min on Arc iGPU. `start_period` in compose
# swallows that window; here we keep it long as a safety net for `docker run`.
HEALTHCHECK --interval=30s --timeout=10s --start-period=45m --retries=3 \
    CMD curl -fsS http://localhost:5001/api/readiness || exit 1

CMD ["python3", "-m", "backend.main_server"]
