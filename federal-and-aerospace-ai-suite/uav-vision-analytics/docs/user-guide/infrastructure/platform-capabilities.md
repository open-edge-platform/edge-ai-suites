<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Infrastructure software Capabilities

## Collecting a Platform Report with system-info.sh

`system-info.sh` is a diagnostic script for Intel Panther Lake systems provisioned using Infrastructure software. After provisioning, the script is available on the target system at `/opt/edge/developer/tools/system-info/`.

### Summary of Tools

- Common tools: `bash`, `lscpu`, `lsblk`, `ip`, etc.
- Optional tools for a more complete report: `dmidecode`, `turbostat`, `intel_gpu_top`, `vulkaninfo`, `vainfo`, `clinfo`, `fwupdmgr`
- `sudo` recommended for full visibility (firmware, DMI, turbostat, dmesg)

### Running the script

```bash
cd /opt/edge/developer/tools/system-info
sudo ./system-info.sh
```

Save output to a file:

```bash
sudo ./system-info.sh > sys-info.txt 2>&1
```

> **Note:** If Panther Lake is not detected (CPUID mismatch), the script still runs and reports what it finds. Some sections show "not installed" warnings when optional tools are missing.

## Output Sections Reference

The script produces the following sections. Use this table to navigate the output.

| Section | What it covers |
|---|---|
| **SYSTEM INFO** | Script version, hostname, kernel, OS, uptime, `hostnamectl` output |
| **PANTHER LAKE PLATFORM CHECK** | CPUID validation (family/model/stepping), microcode, Secure Boot state, Pantherlake-relevant firmware blobs (`xe`, `huc`, `gsc`, `vpu_50xx`) |
| **CPU INFO** | `lscpu` full output, hybrid P/E/LP-E core topology and capacities, per-CPU frequency table, `intel_pstate` governor/HWP settings, cache hierarchy (L1/L2/L3), ISA flags (AVX, AVX-VNNI, AES, SHA, etc.), hardware vulnerability mitigations, live CPU usage, top 5 CPU-consuming processes, `turbostat` summary |
| **MEMORY INFO** | `free -h`, key `/proc/meminfo` fields (hugepages, swap, slabs), DIMM details from `dmidecode` (type, speed, manufacturer, part number), NUMA topology |
| **STORAGE INFO** | `lsblk` block device tree with filesystem and mount points, `df -h` disk usage, NVMe device info (`nvme-cli`), SMART data |
| **NETWORK INFO** | Interface list with IP addresses, default routes, wireless info (`iw`), PCI network device drivers |
| **INTEL GPU INFO** | PCI VGA devices, `/sys/class/drm` device details (vendor/device/revision, GT0/GT1 frequencies), `xe` kernel module info, `intel_gpu_top` utilisation sample, OpenGL/Mesa renderer, Vulkan info, VA-API profiles and entrypoints (`vainfo`) |
| **INTEL NPU INFO** | PCI accelerator device (`8086:b03e`), `/sys/class/accel` details, `intel_vpu` driver version and firmware version, NPU firmware blobs, relevant `dmesg` messages |
| **INTEL COMPUTE / AI RUNTIMES** | OpenCL platform/device details (`clinfo`) — EUs, device IP, USM capabilities; Level Zero library inventory; OpenVINO version and available device list (`CPU`, `GPU.0`–`GPU.7`, `NPU`); oneAPI/DPC++ runtime library paths |
| **INTEL USERSPACE PACKAGES (dpkg)** | Installed Intel packages grouped by: CPU/platform/monitoring, GPU/media/display, NPU/AI/OpenVINO/oneAPI, kernel and firmware |
| **THERMALS, POWER, FANS** | `lm-sensors` output, thermal zone temperatures, cooling device states, RAPL powercap zones (long-term/short-term power limits), battery/power supply state |
| **FIRMWARE / BIOS / SECURITY** | SMBIOS CPU and board details (`dmidecode`), UEFI boot confirmation, TPM state, `fwupd` firmware versions for CPU microcode, display controller, NVMe SSD, system firmware, BootGuard |
| **PCI / USB DEVICE SUMMARY** | Full Intel® PCI device list (BDF, class, device ID), all PCI devices, USB bus/device topology |
| **DMESG: LAST 30 INTEL-RELATED LINES** | Filtered dmesg lines for `xe`, `intel_vpu`, and related Intel driver messages |
| **RECOMMENDED PACKAGES FOR INTEL PANTHER LAKE** | `apt install` commands grouped by: kernel/firmware, core diagnostics, GPU/media, OpenCL/Level Zero, NPU/OpenVINO, useful extras |

## Provisioned System Profile

The following tables describe what is expected to be present on a system that has been provisioned using the Infrastructure software. They cover the four key layers of a provisioned edge node: the underlying platform components, the AI and compute environment, the system services, and the orchestration stack.

### Platform Components

| Component | Detail |
|---|---|
| Platform | Intel® Panther Lake Client Platform |
| ISA extensions | SSE4.2, AVX, AVX2, AVX-VNNI, AES-NI, SHA-NI, VAES, VPCLMULQDQ, GFNI, MOVDIRI, MOVDIR64B (no AVX-512 / AMX) |
| CPU governor | `intel_pstate` / `powersave`; HWP active, turbo enabled; |
| OS | Ubuntu OS Version 24.04 LTS (`minimal-desktop-ubuntu`) |
| Kernel | `linux-image-6.18-intel 260717T053932Z-r2`; command line: `xe.max_vfs=7 xe.force_probe=* modprobe.blacklist=i915 udmabuf.list_limit=8192` |
| iGPU | `xe` driver 1.1.0; device `8086:b08f`; 8 Physical Functions (PFs), 7 SR-IOV Virtual Functions (VFs); persisted via `intel-sriov-vf.service` |
| iGPU firmware | `ptl_guc_70.bin.zst`, `ptl_huc.bin.zst`, `ptl_gsc_1.bin.zst` |
| NPU (NPU 5) | `intel_vpu` 1.0.0 (in-kernel); firmware `vpu_50xx_v1.bin` (Jun 30, 2026); `intel-level-zero-npu 1.35.0.20260722-29947505341~ubuntu24.04` |
| Ethernet | Intel® I226-V (`8086:57b4`); `igc` driver; managed via netplan/NetworkManager |
| Firmware | `PTLPFWI1.R00.4063.D78.2606180911` (2026-06-18); Secure Boot disabled (Setup Mode) |

### AI and Compute Environment

| Component | Detail |
|---|---|
| OpenCL | `intel-opencl-icd 26.27.39122.11-0`; device capabilities were not reported because `clinfo` was not installed |
| Level Zero | `libze1` and `libze-dev 1.32.0`; `libze-intel-gpu1 26.27.39122.11-0`; `intel-level-zero-npu 1.35.0.20260722-29947505341~ubuntu24.04` |
| oneAPI Deep Neural Network Library (oneDNN) | No installed oneDNN package was recorded in the captured report |
| oneAPI TBB | `libtbb12`, `libtbbbind-2-5`, and `libtbbmalloc2 2021.11.0-2ubuntu2` |
| VA-API / media | iHD driver `26.2.3`; `intel-media-va-driver-non-free 26.2.3-1ppa1~noble1`; `libva 2.23.0-1ppa1~noble3`; `libvpl2 1:2.16.0-1ppa1~noble1` |
| GStreamer framework | Full plugin set that comprises base, good, bad, ugly, OpenCV, RTSP, and Qt5 |
| Mesa | `mesa-vulkan-drivers` and `mesa-libgallium 26.0.3-1ppa1~noble1` |
| Container Device Interface (CDI) | GPU specification generator written in Go programming language and built from source; NPU generator script |
| Developer tools | `edge-node-infrastructure-blueprint` repo at `/opt/edge/developer/`; `system-info.sh` at `/opt/edge/developer/tools/system-info/` |

### Services

| Service | Detail |
|---|---|
| Network Time Protocol (NTP) | `chrony` installed and enabled; configurable via `/etc/chrony/chrony.conf` |
| Precision Time Protocol (PTP) | `linuxptp` available for precision time protocol |
| Container runtime | Docker `27.5.1`, containerd, Buildx, and Compose plugin `v2.33.1` (active when `host_type=container`) |
| Kubernetes server | K3s `v1.32.3+k3s1` single-node server (active when `host_type=kubernetes`); traefik disabled |
| SR-IOV | `intel-sriov-vf.service` — provisions and persists 7 GPU VFs across reboots |
| Power profiling | `set_power_profile.sh` for runtime package-power limits: `LowPower` (10 W), `BalancedLow` (15 W), `BalancedHigh` (20 W), `Performance` (25 W), `MaxPerformance` (platform maximum), or `Custom` targets |
| Thermal profiling | `thermald` policy managed by `set_thermal_profile.sh`; staged Fan/Processor/`intel_powerclamp` trips with `cool`, `warm`, `hot`, `thermal-max`, and `custom` profiles; optional CHRG cooling device and kernel-default fallback |
| GPU monitoring | `intel-gpu-tools 1.28` (`intel_gpu_top`) |
| Network performance and profiling | `iperf3`, `linuxptp`, and `tcpdump` |

### Kernel Performance and Debug Tooling

User-space tools sourced from the Intel® Linux overlay (`linux-tools/`) and aligned with the installed kernel `linux-image-6.18-intel` build. They provide tracing, profiling, BPF, CPU power control, and related diagnostics tied to the running kernel.

| Package | Detail |
|---|---|
| `bpftool` | Inspect and manage eBPF programs, maps, links, and BTF metadata loaded in the kernel |
| `hyperv-daemons` | Microsoft Hyper-V integration daemons (KVP, VSS, fcopy) for running the image as a Hyper-V guest |
| `intel-sdsi` | Intel® Software Defined Silicon (SDSi) provisioning and feature-activation utility |
| `libcpupower1` | Shared runtime library used by `cpupower` and other CPU frequency / idle tools |
| `libcpupower-dev` | Development headers for `libcpupower` to build custom CPU power tooling |
| `linux-bpf-dev` | Kernel BPF UAPI headers required to compile BPF programs against this kernel |
| `linux-config-6.18` | Exact `.config` used to build the installed `6.18-intel` kernel |
| `linux-cpupower` | `cpupower` CLI for CPU frequency governors, idle states, and turbo / HWP control |
| `linux-kbuild` | Kernel build infrastructure (scripts, host tools) needed for out-of-tree module builds |
| `linux-misc-tools` | Miscellaneous in-tree user-space tools (e.g. `x86_energy_perf_policy`, `tmon`, `bootconfig`, `gpio`/`iio`/`pci`/`spi`/`usb`/`wmi` utilities) |
| `linux-perf` | `perf` profiler for hardware counters, sampling, tracing, and flame-graph workflows |
| `rtla` | Real-Time Linux Analysis tool for latency tracing (`osnoise`, `timerlat`, `hwnoise`) |
| `usbip` | USB-over-IP client/server for exporting and attaching USB devices across the network |

### Orchestration

| Component | Detail |
|---|---|
| Host type dispatch | `kubernetes`: K3s and Helm and device plugins; `container`: Docker and containerd |
| Helm tool | version 3.x — deployed via `get-helm-3` during provisioning |
| Intel® device plugins | Node Feature Discovery (NFD), GPU plugin, NPU plugin — deployed as Helm charts |
| SR-IOV accelerated containers | VF provisioning and CDI GPU specifications help enable passthrough to containers via device plugin |
| NPU accelerated containers | CDI NPU generator and Intel® NPU device plugin for workload scheduling to NPU |
| Provisioning scripts | `/opt/edge/scripts/` — `kubernetes-provision.sh`, `container-provision.sh`, `setup-kernel-depended-pkgs.sh` |

<!--hide_directive
:::{toctree}
:hidden:

Container Device Interface Guide <./configure-cdi.md>
GPU and NPU Device Plugins <./configure-device-plugins.md>
Power Profiles User Guide <./power-profiles.md>
Thermal Profiles User Guide <./thermal-profiles.md>
Power and Thermal Profiles Co-working Guide <./power-and-thermal-profiles.md>

:::
hide_directive-->
