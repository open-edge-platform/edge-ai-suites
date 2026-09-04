# AI Playground — FedAero Setup Guide

AI Playground is an open source generative AI application suite for offline Ai chat, code
assistance, document search, image analysis, and image and video generation. All features are
powered by your PC’s Intel® Core™ Ultra with built-in Intel® Arc™ GPU or discrete Intel® Arc™
GPU Series A or B with 8GB+ of vRAM.



**Edge Node Infrastructure software (ENIs)** images ship with GPU, NPU, and compute-runtime
drivers pre-installed. This guide covers how to install and run AI Playground on an ENIs
system.

For more information about AI Playground features, see
[`AI Playground Documentation`](https://github.com/intel/AI-Playground/blob/main/readme.md).
For GPU driver requirements on standalone Ubuntu, see
[`Ubuntu GPU driver installation`](https://github.com/intel/AI-Playground/blob/main/docs/linux-intel-gpu-setup.md).


## Contents

1. [Prerequisites and hardware](#1-prerequisites-and-hardware)
2. [Proxy configuration](#2-proxy-configuration)
3. [Download and install AI Playground](#3-download-and-install-ai-playground)
4. [First run and backend setup](#4-first-run-and-backend-setup)
5. [Verify GPU and NPU are detected](#5-verify-gpu-and-npu-are-detected)
6. [Known ENIs-specific issues and fixes](#6-known-enis-specific-issues-and-fixes)
7. [Uninstall](#7-uninstall)

---

## 1. Prerequisites and hardware

**What ENIs provides (already installed):**

- Intel GPU compute-runtime (`libze-intel-gpu1`, `intel-igc-*`, `intel-gmmlib`)
- Level Zero loader (`level-zero` package, `libze_loader.so.1`)
- Intel NPU userspace driver (`intel-driver-compiler-npu`, `intel-fw-npu`, `intel-level-zero-npu`)
- Vulkan loader and Intel ANV driver (`libvulkan1`, `mesa-vulkan-drivers`) — for llama.cpp GPU
- Kernel with `xe` driver support (kernel ≥ 6.10 or ENIs-supplied 6.18-intel)
- System proxy variables in `/etc/environment`

**Before installing AI Playground, add** UV proxy environment variables to `/etc/environment`
(see §2) — required for the Python backend installer to reach PyPI and HuggingFace. Any other
missing system packages (e.g. `python3-venv`, `libfuse2t64`) are detected and prompted by the
AI Playground UI on first run.

**Minimum specs:**

- Intel Core Ultra Series 1/2/3 with Xe iGPU, or Intel Arc dGPU (A/B series, 8 GB+ vRAM)
- Ubuntu 24.04 (Noble)
- 32 GB system RAM recommended (16 GB minimum for CPU-only LLM)
- ≥ 100 GB free disk space for models and Python venvs



## 2. Proxy configuration

ENIs images ship with `http_proxy` / `https_proxy` already set in `/etc/environment`.
The UV-specific proxy variables still need to be added —
uv (AI Playground's Python package manager) reads `UV_HTTP_PROXY` / `UV_HTTPS_PROXY`
in addition to the standard environment proxy.

### Verify existing proxy

```bash
cat /etc/environment | grep -i proxy
# Should already contain http_proxy=... and https_proxy=...
```

If the proxy entries are missing, add them (replace with the site proxy address):

```bash
sudo tee -a /etc/environment <<'EOF'
http_proxy=http://proxy.example.com:port
https_proxy=http://proxy.example.com:port
HTTP_PROXY=http://proxy.example.com:port
HTTPS_PROXY=http://proxy.example.com:port
no_proxy=localhost,127.0.0.1,::1
NO_PROXY=localhost,127.0.0.1,::1
EOF
```

### Add UV proxy variables

```bash
sudo tee -a /etc/environment <<'EOF'
UV_HTTP_PROXY=http://proxy.example.com:port
UV_HTTPS_PROXY=http://proxy.example.com:port
EOF
```

### Re-login and verify

**Note:** Changes to `/etc/environment` only take effect after a **logout and re-login**.
The GNOME desktop launcher reads the PAM session environment set at login time — it does not
inherit variables exported in a terminal. Skipping the re-login is the most common cause of
backend install failures on ENIs.

After re-login, confirm all proxy vars are present and contain no quote characters:

```bash
printenv | grep -i proxy
# Expected: http_proxy, https_proxy, UV_HTTP_PROXY, UV_HTTPS_PROXY
```



## 3. Download and install AI Playground

### Download the installer

**AI Playground 3.1.2-beta-hf2:**
- [Release Notes](https://github.com/intel/AI-Playground/releases/tag/v3.1.2-beta_hf2)
- [Linux Installer (.deb)](https://github.com/intel/AI-Playground/releases/download/v3.1.2-beta_hf2/AI-Playground-installer.deb)

```bash
curl -fL --proxy "$http_proxy" \
  -o ~/AI-Playground.deb \
  "https://github.com/intel/AI-Playground/releases/download/v3.1.2-beta_hf2/AI-Playground-installer.deb"
```

### Install the .deb

```bash
sudo apt install ~/AI-Playground.deb
```

`apt` resolves the Electron runtime dependencies
(`libgtk-3-0`, `libnss3`, `libasound2`, `pciutils`, `python3`, `git`) automatically.

### Add the user to render and video groups

If not already done by the ENIs image:

```bash
sudo gpasswd -a "$USER" render
sudo gpasswd -a "$USER" video
```

Group changes require a re-login to take effect:

```bash
groups | tr ' ' '\n' | grep -E 'render|video'
```



## 4. First run and backend setup

### Launch AI Playground

After re-login, launch from the application menu (search "AI Playground") or from a terminal.
**Do not launch as root** — Electron refuses to start with `sudo`.

```bash
ai-playground
```

### Hardware Profile

On initial set up, AI Playground detects your hardware profile and selects the appropriate feature mode (Studio, Essentials, Nvidia) to install. For ENIs systems (Intel Core Ultra - Panther Lake ), AI Playground Studio will be selected by default. Leave this as selected.

### Backend installation

For each backend (AI-Backend / OVMS, ComfyUI, LlamaCPP, Home-Agent):

1. Click **Install** in the AI Playground UI
2. The app downloads Python wheels, OVMS binaries, and clones the ComfyUI repository
3. If any system packages are missing (`python3-venv`, `libfuse2t64`, build tools), the UI
   prompts to install them — follow the on-screen instructions
4. ComfyUI installation takes ~5 minutes (XPU torch wheels + insightface compilation)
5. OVMS/AI-Backend installs in ~2 minutes

If any install fails with a network error, confirm proxy settings (§2) and retry from within
the app. Do not reinstall the `.deb`.



## 5. Verify GPU and NPU are detected

### Level Zero (ComfyUI XPU, OpenVINO GPU)

```bash
ldconfig -p | grep -E 'libze_loader|libze_intel_gpu'
# Expected:
#   libze_loader.so.1 => /usr/lib/x86_64-linux-gnu/libze_loader.so.1
#   libze_intel_gpu.so.1 => /usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1
```

### NPU

```bash
ls /dev/accel/accel0                                      # device node must exist
ls /usr/lib/x86_64-linux-gnu/libze_intel_npu.so*          # NPU Level Zero plugin
```

### Render node access

```bash
ls -l /dev/dri/renderD128                                 # must exist
groups | tr ' ' '\n' | grep -E 'render|video'             # user must be in these groups
```

### OpenVINO device enumeration

After installing the AI-Backend:

```bash
~/.local/share/ai-playground/resources/OpenVINO/.venv/bin/python3 -c \
  "import openvino as ov; print(ov.Core().available_devices)"
# Expected: ['CPU', 'GPU', 'NPU']
# GPU missing → Level Zero not found; check ldconfig
# NPU missing → group membership not applied; re-login and retry
```

### ComfyUI XPU (PyTorch)

After installing the ComfyUI backend:

```bash
~/.local/share/ai-playground/resources/ComfyUI/.venv/bin/python3 -c \
  "import torch; print('torch:', torch.__version__); print('xpu devs:', torch.xpu.device_count())"
# Expected: torch: 2.12.x+xpu    xpu devs: 1
# xpu devs: 0 → Level Zero not visible to venv; check ldconfig and re-login
```

---

## 6. Known ENIs-specific issues and fixes

### Backend installation fails with proxy / network errors

**Symptom:** Installing any backend fails with `Connection refused`, `ERR_CONNECTION_TIMED_OUT`,
or git clone errors.

**Cause — proxy not in session environment.** The GNOME desktop launcher starts AI Playground
without proxy variables exported in `~/.profile` or `~/.bashrc`. Only variables in
`/etc/environment` are loaded for desktop-launched processes.

**Fix:** Confirm `/etc/environment` has both the system proxy and UV proxy vars (§2), then
log out and back in. Confirm with `printenv http_proxy UV_HTTP_PROXY` in a new terminal.

### ENIs GPU stack — Level Zero package naming

ENIs ships Level Zero as the `level-zero` package (not `libze1`). These are the same loader
under different package names for different Ubuntu generations. Installing `libze1` from the
Intel apt repo on top of the ENIs `level-zero` package will conflict.

### Disk space — model storage

AI Playground downloads models on first use. Approximate storage per feature:

| Feature               | Model size            |
|-----------------------|-----------------------|
| LLM (OpenVINO / OVMS) | 4–15 GB per model     |
| LLM (llama.cpp, GGUF) | 2–8 GB per model      |
| Image generation      | 5–12 GB per model set |
| NPU chat              | 2–5 GB                |

At least 50–100 GB must be free on the partition containing `~/.local/share/ai-playground/`.
Check before installing backends:

```bash
df -h ~/.local/share
```

Models are stored at `~/.local/share/ai-playground/resources/models/`.

### GPU utilization not visible

**Symptom:** GPU monitoring tools (e.g. `intel_gpu_top`) show no data or fail to start.

**Cause:** ENIs uses the `xe` kernel driver (not `i915`). `intel_gpu_top` does not support
`xe`.

GPU frequency is readable via sysfs without any permission changes:

```bash
cat /sys/class/drm/card0/device/tile0/gt0/freq0/cur_freq   # current GPU MHz
cat /sys/class/drm/card0/device/tile0/gt0/freq0/max_freq
```


## 7. Uninstall

```bash
# Remove AI Playground app:
sudo apt remove ai-playground

# Remove downloaded models and Python venvs (several GB):
rm -rf ~/.local/share/ai-playground

# Remove uv cache (optional):
rm -rf ~/.cache/uv

# Remove UV proxy vars added in §2b (if desired):
sudo sed -i '/UV_HTTP_PROXY\|UV_HTTPS_PROXY/d' /etc/environment
```


