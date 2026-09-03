<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Power Profiles User Guide

## Overview

Intel® Core™ Ultra edge nodes can be tuned to trade sustained performance
against heat, fan noise, and energy use. The Infrastructure software ships a
set of local power-tuning tools under `tools/power-tuning/` that let you:

- Apply a ready-made **power profile** (`LowPower` … `MaxPerformance`).
- Set an explicit **package (PkgWatt)** and optional **platform (SysWatt)** cap.
- **Monitor** live power and package temperature.
- **Stress** the CPU and integrated GPU to validate a profile under load.

> **On the target system:** the commands below use repository-relative paths
> (`tools/power-tuning/…`), which work when you run them from the repo root. On a
> host provisioned with Infrastructure software, the same tools are available on
> the target system at `/opt/edge/developer/tools/power-tuning/`. Either
> `cd /opt/edge/developer` and use the relative paths as written, or prefix each
> command with the full path (e.g.
> `sudo /opt/edge/developer/tools/power-tuning/set_power_profile.sh --list`).

All tuning is enforced through Intel RAPL (Running Average Power Limit) and the
Intel Low Power Mode daemon (`intel_lpmd`). These two layers behave differently
across a reboot:

- The **RAPL power cap** (the PL1/PL2 wattage limits) is programmed into volatile
  CPU registers and **reverts automatically on reboot** to firmware defaults.
  This is the main enforcement and the built-in safety net. The **thermald
  profile also acts on these limits**: applying the profile initializes
  thermald's RAPL cooling device and reconfigures the effective power limit from
  the PPCC value embedded in the thermal profile.
- The **`intel_lpmd` config file** is written to disk, so it **persists across a
  reboot** and is re-read by the daemon on the next boot. To undo the daemon-side
  tuning you must restore the config (see
  [What persists across a reboot](#what-persists-across-a-reboot)).

> **Note:** These tools are tuned for Intel Panther Lake (Core Ultra). On other
> Intel silicon they still run, but the Config-TDP (cTDP) levels and the
> platform (psys/SysWatt) domain may differ or be unavailable.

## Prerequisites

- An Intel `x86_64` host (Core Ultra / Panther Lake recommended).
- A CPU frequency governor can conflict with `intel_lpmd`. The `performance` and
  `ondemand` governors override the daemon's low-power intent, so either switch
  to `powersave` — which cooperates with `intel_lpmd` — or disable the governor
  service altogether:

  ```bash
  # Option 1: switch to the powersave governor
  echo powersave | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

  # Option 2: disable the governor service
  sudo systemctl disable --now powersave.service
  ```
- Linux ships several competing power-management daemons. Stop and disable any
  that are running — for example `tlp`, `tuned`, `cpufreqd`, or `ondemand` — so
  they will conflict with `intel_lpmd` for control of CPU power and frequency.
  -
- BIOS settings that hand CPU power/frequency control to the OS. The power
  limits and EPP/EPB tuning only take effect when the OS (not firmware) owns
  these controls — verify them **before** applying a profile, or the script may
  succeed while the limits are silently ignored.
  Setting names and menu paths vary by vendor. See the **BIOS Settings**
  sections in [set-power-profile skill](https://github.com/open-edge-platform/edge-node-infrastructure-blueprint/blob/main/skills/set-power-profile/SKILL.md)
  for the full mandatory list plus optional settings (e.g. disabling firmware
  DBPM, unlocking the power-limit MSRs, and *Config Base Power* / cTDP). `sudo` access. The power scripts read/write MSRs and restart a system service,
  so they re-run themselves with `sudo`.
- `msr` kernel module and `msr-tools` (`rdmsr` / `wrmsr`) — required to read the
  cTDP levels and program the RAPL MSRs:

  ```bash
  sudo modprobe msr
  sudo apt-get install -y msr-tools
  ```

- `turbostat` for monitoring (from the matching `linux-tools` package):

  ```bash
  sudo apt-get install -y linux-tools-$(uname -r)
  ```

- `stress-ng` for load generation:

  ```bash
  sudo apt-get install -y stress-ng
  ```


## Power Profiles

A profile is a package-power (PkgWatt) budget plus a default burst ratio. The
package cap is enforceable on every platform; on silicon that also exposes the
psys (SysWatt) domain, a matching whole-platform cap is added automatically.

> **Note:** The table below is a reference recommendation. The values can be
> overridden with command-line parameters (e.g. `--pkgWatt`, `--sysWatt`,
> `--burstRatio`, `--pl1Tau`) for further tuning — see
> [Set an Explicit Power Envelope](#set-an-explicit-power-envelope).

| Profile | PkgWatt budget | Default burst ratio | Typical use |
|---|---|---|---|
| `LowPower` | 10 W | 1.25 | Fanless / battery, mostly idle (kiosk, signage, sensor) |
| `BalancedLow` | 15 W | 1.25 | Light interactive (basic UI, browsing) |
| `BalancedHigh` | 20 W | 1.18 | Interactive / mixed workloads |
| `Performance` | 25 W | 1.19 | Steady general compute |
| `MaxPerformance` | platform max (cTDP Level 2) | 1.18 | Sustained heavy compute (AI inference, transcode, builds) |
| `Custom` | (none) | (none) | Explicit `--pkgWatt` / `--sysWatt` / `--burstRatio` values |

### Terminology

| Term | Meaning |
|---|---|
| PkgWatt | Package power — the CPU cores plus the integrated GPU. The main limit these tools set. |
| SysWatt | Platform power — the whole board (package plus memory, VRs, other rails). Exposed by the RAPL psys domain. **Not available on all systems:** many Core Ultra platforms do not expose a psys domain at all (any `--sysWatt` is then ignored and only the PkgWatt cap applies), and on some silicon the counter is present but frozen, so it reads `0.00`. Use PkgWatt as the reliable effective figure. |
| PL1 | Power Limit 1 — the **sustained** power allowed over the long term. |
| PL2 | Power Limit 2 — the **short burst** power the chip may briefly reach. `PL2 = PkgWatt × burst_ratio`. |
| burst_ratio | The multiplier that sets the burst limit (PL2) relative to the sustained limit (PL1): `PL2 = PkgWatt × burst_ratio`. It controls how much extra power the chip may draw for short spikes before settling back to the sustained budget. `1.0` means no burst (PL2 = PL1, flat power); `1.25` allows bursts 25% above sustained (e.g. a 20 W PkgWatt budget bursts to 25 W). Higher values feel snappier under sudden load; lower values give flatter, more predictable power and temperature. |
| tau (PL1 tau) | Time window (seconds) over which PL1 is averaged — how long a burst can last before settling to PL1. |
| cTDP Level 2 | Configurable TDP — the highest sustained power the silicon supports (the maximum you can request). |

## Apply a Named Profile

Use `set_power_profile.sh` with `--profile`. Run from the repository root.
On the target system, the tools are available at `/opt/edge/developer/tools/power-tuning/` —
either `cd /opt/edge/developer` and use the relative paths as written, or prefix
each command with the full path (e.g.
`sudo /opt/edge/developer/tools/power-tuning/set_power_profile.sh --profile LowPower`):

```bash
# List the available profiles and their PkgWatt budgets
tools/power-tuning/set_power_profile.sh --list

# Longest battery / coolest, silent operation
sudo tools/power-tuning/set_power_profile.sh --profile LowPower

# Balanced interactive use
sudo tools/power-tuning/set_power_profile.sh --profile BalancedHigh

# Max sustained throughput (AI inference / transcode / builds)
sudo tools/power-tuning/set_power_profile.sh --profile MaxPerformance

# Override the default burst ratio for a snappier feel
sudo tools/power-tuning/set_power_profile.sh --profile Performance --burstRatio 1.4

# Profile PkgWatt with an explicit SysWatt cap (psys-capable platforms only)
sudo tools/power-tuning/set_power_profile.sh --profile Performance --sysWatt 35

# Preview only — resolve and print the plan without changing anything
tools/power-tuning/set_power_profile.sh --profile Performance --dry-run
```

> **`--sysWatt` is not honored on every platform.** The SysWatt cap only takes
> effect on silicon that exposes the RAPL psys domain. On platforms without it,
> `--sysWatt` is silently ignored and only the PkgWatt cap is enforced; on
> platforms where the psys counter is present but frozen, the cap is written but
> `turbostat` still reads a fixed value (`SysWatt = 0.00`, or any other constant
> that never changes with load). In both cases PkgWatt is the reliable effective
> figure. The `--dry-run` output reports whether psys is supported on this host.

## Set an Explicit Power Envelope

For fine-grained control, set the package (and optionally platform) watts
directly instead of a named profile.

```bash
# Sustained 20 W with the default 1.25 burst ratio (PL2 = 25 W)
sudo tools/power-tuning/set_power_profile.sh --pkgWatt 20

# Strict cap — no burst (PL1 = PL2 = 30 W)
sudo tools/power-tuning/set_power_profile.sh --pkgWatt 30 --burstRatio 1.0

# Independent platform cap: PkgWatt 25 W, SysWatt 35 W
sudo tools/power-tuning/set_power_profile.sh --pkgWatt 25 --sysWatt 35

# Custom PL1 time window (tau) of 10 s
sudo tools/power-tuning/set_power_profile.sh --pkgWatt 15 --pl1Tau 10
```

| Option | Meaning |
|---|---|
| `--pkgWatt W` | Package PL1 (sustained) target. Clamped to `[0.125 W, cTDP Level 2]` and snapped to the RAPL power-unit granularity (0.125 W). Default: Nominal TDP. |
| `--sysWatt W` | psys/platform (SysWatt) cap. Applied only on platforms that expose the psys domain; ignored otherwise. Default: same as PkgWatt. |
| `--burstRatio R` | Burst ratio (`>= 1.0`). `PL2 = pkgWatt × R`, clamped to cTDP Level 2. Also biases EPP/EPB toward performance. |
| `--pl1Tau S` | PL1 time window in seconds (default `28`). |
| `--dry-run` | Resolve and print the plan without applying anything. |
| `--list` | List available profiles and exit. |

## Monitor Power and Temperature

> **Note:** `pt_mon.sh` is provided as a *reference* monitor. You can use it,
> or any other power-monitoring tool you prefer (e.g. `turbostat`, `powertop`,
> `intel_gpu_top`, a BMC/OEM utility, or reading
> `/sys/class/powercap/intel-rapl*`). The power profile and stress steps are
> independent of which monitor you choose.

Watch package temperature and the RAPL power domains live with `pt_mon.sh`
(wraps `turbostat`). It samples every 2 s and tees to `pt_mon.txt`:

```bash
cd tools/power-tuning
sudo ./pt_mon.sh
```

For a custom interval, duration, or log path, run `turbostat` directly with the
same columns:

```bash
sudo turbostat -S --interval 1 --num_iterations 60 \
  --show PkgTmp,PkgWatt,CorWatt,GFXWatt,RAMWatt,SysWatt \
  | tee pt_mon.txt
```

| Column | Meaning |
|---|---|
| `PkgTmp` | CPU package temperature (°C). |
| `PkgWatt` | Whole-package power (cores + iGPU + uncore) — the most reliable effective figure. |
| `CorWatt` | CPU cores portion of the package. |
| `GFXWatt` | Integrated GPU (graphics) portion. |
| `RAMWatt` | DRAM/memory RAPL domain. |
| `SysWatt` | Platform (psys) power; reads `0.00` when the counter is frozen or absent. |

## Stress the Platform Under Load

> **Note:** `stress_gen.sh` provides a *simulated* load for evaluation purposes.
> You can use it, or run the **actual workload** you want to evaluate — apply the
> power profile, start the monitor, and drive the platform with either the
> simulated stress below or your real application. The monitor reacts the same
> way to either.

Validate a profile or cap under real load with `stress_gen.sh` (wraps
`stress-ng`). No `sudo` needed — it runs as the current user:

```bash
# All CPUs at 100% + 12 iGPU workers, until Ctrl-C
tools/power-tuning/stress_gen.sh

# 4 CPU workers at 80%, no GPU load, for 2 minutes
tools/power-tuning/stress_gen.sh --cpus 4 --load 80 --gpu 0 --duration 2m

# CPU + iGPU burn-in for 5 minutes
tools/power-tuning/stress_gen.sh --gpu 8 --duration 5m
```

| Option | Meaning |
|---|---|
| `--cpus N` | Number of CPU workers, `1..nproc` (default: all CPUs). |
| `--load P` | Per-CPU load percentage, `1..100` (default `100`). |
| `--gpu N` | Number of stress-ng iGPU worker processes, `0..12` (default `4`; `0` disables GPU load). This is a worker count, not a GPU count. Use a maximum of `4` for a 4 Xe-core iGPU and `8` for a 12 Xe-core iGPU. |
| `--duration D` | Run time in stress-ng syntax (`60s`, `5m`, `2h`); omit to run until stopped. |

Stop a running stress test with `Ctrl-C`, or:

```bash
sudo pkill -x stress-ng
```

### Real AI inference load with `openvino_stress.sh`

For a load that resembles a production edge workload rather than a synthetic one,
`openvino_stress.sh` drives the CPU, GPU, or NPU with OpenVINO `benchmark_app`
running in a container (K3s pod or Docker, auto-detected). This is useful for
measuring throughput-per-watt and for thermal qualification with a real
neural-network compute pattern:

```bash
# 120 s of CPU inference load
tools/power-tuning/openvino_stress.sh --device cpu --duration 120

# 5 min of GPU inference load
tools/power-tuning/openvino_stress.sh --device gpu --duration 300

# NPU inference for a fixed number of iterations
tools/power-tuning/openvino_stress.sh --device npu --niter 500000

# Stop and remove any running benchmark containers/pods
tools/power-tuning/openvino_stress.sh --cleanup
```

| Option | Meaning |
|---|---|
| `--device cpu\|gpu\|npu` | Target accelerator (default `cpu`). |
| `--runtime k3s\|docker` | Container runtime (default: auto-detect). |
| `--niter N` | Iteration count; `0` = time-based (default `0`). |
| `--duration D` | Run time in seconds when `niter=0` (default `60`). |
| `--api sync\|async` | Inference API mode (default `sync`). |
| `--cleanup` | Stop and remove running benchmark containers/pods. |

The default model is downloaded automatically on first run; override the model,
image, or thread count with `--model`, `--image`, and `--nthreads`.

## Recommended Workflow

To validate a power profile end to end, use three terminals:

1. **Apply** the profile:

   ```bash
   sudo tools/power-tuning/set_power_profile.sh --profile Performance
   ```

2. **Monitor** power and temperature:

   ```bash
   cd tools/power-tuning && sudo ./pt_mon.sh
   ```

3. **Stress** the platform and watch the monitor react:

   ```bash
   tools/power-tuning/stress_gen.sh --duration 3m
   ```

   `stress_gen.sh` is a simulated load; substitute the real workload you want to
   evaluate here if you prefer — for example a real AI inference load with
   `tools/power-tuning/openvino_stress.sh --device gpu --duration 3m`.

Step up one profile at a time until throughput stops improving or the package
temperature approaches the throttle point.

## Side Effects and Tips

- **Thermals & acoustics:** higher profiles raise package temperature and fan
  noise; lower profiles run cooler and quieter (or fanless).
- **Throttling:** if cooling can't keep up, the firmware clamps sustained power
  below the target. The script reports the effective (enforced) value and notes
  when firmware clamped PL1.
- **`SysWatt = 0.00`:** on some Core Ultra silicon the psys counter is frozen.
  The cap is still written, but turbostat can't observe it — use PkgWatt as the
  effective figure. This is a firmware limitation, not a failure.
- **Brief management gap:** applying a profile restarts `intel_lpmd.service`
  (~2 s) during which the daemon isn't actively managing CPU states.
- **Partial revert on reboot:** the RAPL power cap resets to firmware defaults
  on reboot, but the `intel_lpmd` config on disk does not — see below.

## What Persists Across a Reboot

The script changes two independent things with different lifetimes:

| What changes | Where it lives | Reverts on reboot? |
|---|---|---|
| RAPL cap (PL1/PL2 watts) | Volatile CPU RAPL MSRs (`0x610`/`0x65C`) + powercap sysfs | **Yes** — firmware re-initializes these on every boot. |
| `intel_lpmd` config (EPP/EPB, ITMT, active CPUs) | `intel_lpmd_config.xml` on disk (and any model-specific file it overrides) | **No** — the file stays on disk and `intel_lpmd` re-reads it at the next boot. |

So on reboot `intel_lpmd` **re-uses the config file the script wrote** (assuming
`intel_lpmd.service` is enabled at boot); the daemon-side tuning is not undone by
a reboot — only the wattage cap is.

To restore the stock daemon behavior, put the original config back. The script
saves a one-time `.orig` backup of any model-specific file it overrides (e.g.
`intel_lpmd_config_F6_M204.xml` on Panther Lake):

```bash
sudo cp -a /usr/local/etc/intel_lpmd/intel_lpmd_config_F6_M204.xml.orig \
           /usr/local/etc/intel_lpmd/intel_lpmd_config_F6_M204.xml
sudo systemctl restart intel_lpmd.service
```

> **Note:** Only overridden *model-specific* files get an `.orig` backup. The
> generic `intel_lpmd_config.xml` the script writes has no backup if no config
> existed there before.

## Related Agent Skills

The same tools are also driven by agent skills (see
[AI Agent Integration](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/agent-skills.html)):

| Skill | Purpose |
|---|---|
| `set-power-profile` | Apply a named power profile or set an explicit PkgWatt / SysWatt envelope. |
| `monitor-power-thermal` | Run the live power/thermal monitor. |
| `generate-platform-stress` | Generate configurable CPU / iGPU load. |

These power skills run **directly on the target host** — they read/write the
CPU's RAPL MSRs and restart `intel_lpmd`, which must happen locally on the node.
To drive them by natural language on a provisioned node, install an agent CLI on
the target host and open it in the developer source tree (`/opt/edge/developer`),
where the `skills/` directory and `tools/power-tuning/` scripts already live.

### Install the Claude Code CLI on the Target Host (Ubuntu)

```bash
# Install Claude Code
curl -fsSL https://claude.ai/install.sh | sh

# If Node.js is already installed, you can instead use npm:
# npm install -g @anthropic-ai/claude-code

# Ensure the install location is on PATH (add to ~/.bashrc to persist)
export PATH="$HOME/.local/bin:$PATH"

# Verify
claude --version
```
Sign in to your Claude account on first launch to use the latest models.

Then launch the agent from the developer source tree so it can discover the
skills and scripts:

```bash
cd /opt/edge/developer
claude
```

From there, prompt in natural language — e.g. *"switch this node to the
Performance power profile"* or *"stress all CPUs for 3 minutes and monitor
power"* — and the agent runs the matching skill against the local
`tools/power-tuning/` scripts.
