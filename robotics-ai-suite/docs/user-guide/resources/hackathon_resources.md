---
orphan: true
---

# Hack-a-thon Resources

The below [software stack](https://amrdocs.intel.com/downloads/hackathon_install.zip) has been pre-installed on your system. Feel free to review and launch Physical AI Studio when ready to get started. For launch instructions, see [Daily Use After Installation](#daily-use-after-installation).

# Intel Edge AI / Robotics Stack — Script-Based Installation & Verification

**Target:** Ubuntu 24.04 LTS (HWE kernel) · Intel Core Ultra / Arc (NPU + iGPU)
**Stack:** NPU Driver → iGPU Driver → Miniforge3 (`intel_dev_env`) → Physical AI Studio → OpenVINO 2026.3 → Anomalib v2.6.0 → LeRobot (PyTorch XPU) → VS Code

## Package Contents

| File | Purpose |
|---|---|
| `1_install_drivers.sh` | Installs Intel NPU + iGPU drivers (**reboot required after**) |
| `2_install_software.sh` | Installs Miniforge3, `intel_dev_env`, Physical AI Studio, OpenVINO, Anomalib, LeRobot (+PyTorch XPU swap), VS Code |
| `verify_stack.py` | Python script that functionally tests every installed component |
| `intel-edge-ai-stack-installation-guide.md` | Full manual step-by-step guide (reference / troubleshooting) |
| `README.md` | This document |

---

## Installation Workflow

### Step 0 — Preparation

Copy all files to the target machine, then:

```bash
chmod +x 1_install_drivers.sh 2_install_software.sh
```

Confirm the OS and kernel meet requirements:

```bash
lsb_release -a    # expect Ubuntu 24.04
uname -r          # expect kernel >= 6.8 (HWE); NPU needs >= 6.6
```

> ⚠️ Run all scripts as a **normal user** (not root / not with `sudo` in front). They call `sudo` internally where needed.

### Step 1 — Install the drivers

```bash
./1_install_drivers.sh
```

What it does:
- **Intel NPU driver** — purges old NPU packages, installs dependencies (`libtbb12`), downloads the release tarball from `github.com/intel/linux-npu-driver`, installs the `.deb` packages, ensures the Level Zero loader (`libze1`), and adds you to the `render` group.
- **Intel iGPU driver** — adds the `ppa:kobuk-team/intel-graphics` PPA, installs the compute runtime (OpenCL + Level Zero GPU) and media (VA-API) packages, and adds you to the `render` and `video` groups.

> 📝 If the NPU download fails, a newer release has likely replaced the pinned one. Check https://github.com/intel/linux-npu-driver/releases and update the `NPU_DRIVER_VERSION` / `NPU_DRIVER_TARBALL` variables at the top of `1_install_drivers.sh`.

### Step 2 — Reboot (mandatory)

```bash
sudo reboot
```

The reboot loads the `intel_vpu` kernel module and applies the new group memberships. **Do not skip this** — every later GPU/NPU check will fail without it.

After reboot, quick-verify the drivers:

```bash
ls /dev/accel/accel0            # NPU device node exists
sudo dmesg | grep intel_vpu     # "Initialized intel_vpu ..." with no errors
clinfo | grep "Device Name"     # Intel GPU listed
vainfo                          # VA-API profiles listed
```

### Step 3 — Install the software stack

```bash
./2_install_software.sh
```

What it does, in order:
1. **Miniforge3 + `intel_dev_env`** — installs conda (conda-forge default channel) to `~/miniforge3`, creates the `intel_dev_env` environment (Python 3.11). All Python packages below go into this one environment.
2. **Physical AI Studio** — installs `uv` and `nvm`, clones the repo to `~/physical-ai-studio`, syncs the backend with the Intel XPU extra (`uv sync --extra xpu`), and builds the UI. *Setup only — launch commands are printed at the end.*
3. **OpenVINO 2026.3** — pip install into `intel_dev_env`, then prints the available devices (expects `['CPU', 'GPU', 'NPU']`).
4. **Anomalib v2.6.0** — installed with the `[xpu,openvino]` extras.
5. **LeRobot + PyTorch XPU swap** — installs system ffmpeg/PyAV build libraries, installs LeRobot, then **uninstalls the CUDA-backed torch wheels LeRobot pulls in and reinstalls PyTorch from the XPU wheel index** (`download.pytorch.org/whl/xpu`). Verifies `torch.xpu.is_available()`.
6. **VS Code** — installs from the official Microsoft apt repository plus the Python and Jupyter extensions.

The script starts with a driver sanity check and warns if it looks like Step 1/2 were skipped.

**Partial runs** (e.g., after fixing an error):

```bash
./2_install_software.sh 6 7        # only OpenVINO + Anomalib
./2_install_software.sh --from 6   # OpenVINO onward
```

Both scripts are idempotent — re-running skips what's already installed (Miniforge, the env, git clones, VS Code).

### Step 4 — Verify everything with Python

```bash
conda activate intel_dev_env
python verify_stack.py
```

The verifier goes beyond imports — it **functionally exercises each component**:

| # | Check | What it actually does |
|---|---|---|
| 1 | Python environment | Confirms you're inside `intel_dev_env` |
| 2 | OpenVINO discovery | Import + all three devices (CPU/GPU/NPU) visible |
| 3 | OpenVINO inference | Builds a tiny model in memory and **compiles + runs it on each device**, reporting device name and latency |
| 4 | PyTorch XPU | Verifies the `+xpu` build (catches CUDA wheels sneaking back), `torch.xpu.is_available()`, and runs a **real 512×512 matmul on the GPU** |
| 5 | Anomalib | Import, Patchcore model instantiation, Engine construction |
| 6 | LeRobot | Import + `LeRobotDataset` API loads |
| 7 | Physical AI Studio | Repo/backend presence (non-fatal — it lives in its own uv env) |
| 8 | System devices | `/dev/accel/accel0`, `/dev/dri/renderD*`, render/video group membership |

Output is color-coded PASS/FAIL/WARN per check with a final summary. **Exit code 0** = all required checks passed, **1** = something failed — so it can be chained or used in CI:

```bash
python verify_stack.py && echo "stack ready"
VERBOSE=1 python verify_stack.py     # full tracebacks for debugging
```

Expected healthy output ends with:

```
  ✓ ALL REQUIRED CHECKS PASSED — stack is ready
```

---

## Quick Reference — Full Sequence

```bash
# 1. Drivers
chmod +x 1_install_drivers.sh 2_install_software.sh
./1_install_drivers.sh

# 2. Reboot (mandatory)
sudo reboot

# 3. Software stack
./2_install_software.sh

# 4. Verify
conda activate intel_dev_env
python verify_stack.py
```

## Daily Use After Installation

```bash
conda activate intel_dev_env                  # every new shell

# Launch Physical AI Studio when needed:
cd ~/physical-ai-studio/application/backend && ./run.sh          # terminal 1
cd ~/physical-ai-studio/application/ui && nvm use && npm run start  # terminal 2
# → http://localhost:3000
```

## Additional Resource Links

- [Robotics AI Suite](https://docs.openedgeplatform.intel.com/dev/ai-suite-robotics.html)
- [NPU Driver](https://github.com/intel/linux-npu-driver)
- [iGPU Driver](https://dgpu-docs.intel.com/installation-guides/installing-packages-from-the-intel-ppa.html)
- [Physical AI Studio](https://github.com/open-edge-platform/physical-ai-studio)
- [OpenVINO v2026.3](https://github.com/openvinotoolkit/openvino)
- [Anomalib v2.6.0](https://github.com/open-edge-platform/anomalib)
- [LeRobot](https://github.com/huggingface/lerobot)
- [PyTorch](https://pytorch.org/get-started/additional-platforms/)

## Troubleshooting

| Symptom | Fix |
|---|---|
| `curl: command not found` (or wget/git/gpg) | Fixed in current scripts — both install base tools first. Re-download the zip or `sudo apt install -y curl wget git gpg` and re-run |
| Download fails with `502 Bad Gateway` / `Failed to fetch` from pythonhosted.org | Transient PyPI CDN error — the script now auto-retries 3× with backoff. If it still fails, wait a few minutes and re-run the same step (downloads are cached) |
| `curl: (7) Failed to connect to localhost port 7860` during UI build | The UI API-client build needs the backend running — current script starts it automatically, waits, builds, then stops it. Re-run: `./2_install_software.sh 5` |
| npm "funding" / "vulnerabilities" / "new version" notices | Informational only — safe to ignore |
| NPU tarball download fails | Update `NPU_DRIVER_*` variables in `1_install_drivers.sh` to the latest release |
| `verify_stack.py`: OpenVINO missing `NPU`/`GPU` | Confirm reboot happened; check `/dev/accel/accel0` and `clinfo`; re-run `./1_install_drivers.sh` |
| `torch.xpu.is_available()` False | Re-run the swap: `./2_install_software.sh 8` |
| torch version has `+cu1xx` suffix | CUDA wheels came back (e.g., after a `pip install` pulled torch) — re-run `./2_install_software.sh 8` |
| `conda: command not found` | `~/miniforge3/bin/conda init bash && source ~/.bashrc` |
| Group membership WARN in verifier | Log out/in (or reboot) so `render`/`video` groups apply |

For full manual steps, package details, and deeper troubleshooting, see `intel-edge-ai-stack-installation-guide.md`.
