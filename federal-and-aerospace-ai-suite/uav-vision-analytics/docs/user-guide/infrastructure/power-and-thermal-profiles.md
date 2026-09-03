<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Power and Thermal Profiles Co-working Guide

## Overview

Use the power and thermal profiles together to control both sides of the same
thermal budget:

- `set_power_profile.sh` limits heat generation by setting a package-power
  envelope (RAPL PL1/PL2 and `intel_lpmd` tuning).
- `set_thermal_profile.sh` sets the response when package temperature rises
  (fan, processor frequency cap, then `intel_powerclamp`).

The power profile is the upper bound on sustained package power. The thermal
profile is a protection policy, not a second power-profile selector. A thermal
trip can reduce performance below the power target, but it cannot raise power
above the RAPL cap.

> Run both tools directly on the target system. On a provisioned node their
> absolute paths are under `/opt/edge/developer/tools/power-tuning/`.

## Acronyms and Terms

| Term | Meaning |
|---|---|
| cTDP | Configurable Thermal Design Power. The platform-defined range of sustained processor power; Level 2 is the highest supported target. |
| `intel_lpmd` | Intel Low Power Mode daemon. The power-profile tool configures it to apply CPU energy-performance tuning. |
| MSR | Model-Specific Register. Low-level CPU register used to program the RAPL power limits. |
| PL1 | Power Limit 1. The long-term, sustained package-power limit. |
| PL2 | Power Limit 2. The short-duration burst package-power limit above PL1. |
| PPCC | Power Participant Capabilities Collection. The thermald configuration block that supplies a package power limit to thermald. |
| PkgTmp | CPU package temperature reported by `turbostat`, in degrees Celsius. |
| PkgWatt | CPU package power reported by `turbostat`; includes CPU cores, integrated GPU, and uncore power. |
| RAPL | Running Average Power Limit. Intel hardware interface used to read and enforce package and platform power limits. |
| SysWatt | Whole-platform power reported by `turbostat` through the optional RAPL psys domain. |
| psys | RAPL platform-power domain that supplies the SysWatt limit and reading when supported by the system firmware. |

## Interaction and Dependency

The profiles intentionally share the package RAPL PL1 setting. When applying a
thermal profile, the script reads the current package PL1 and writes it into
the generated thermald configuration as a PPCC maximum. thermald then applies
that value when it starts.

This makes the order mandatory:

1. Apply the power profile.
2. Apply the thermal profile.
3. Start monitoring before running a workload or stress test.

If thermal is applied first, or thermald is restarted after a later power
change, thermald can reset the package PL1 to the PPCC value saved in its
existing configuration. Applying the thermal profile again after the power
profile refreshes that PPCC value. Always use the same order when changing the
power target.

On platforms without the RAPL psys domain, `SysWatt` is not supported. Track
`PkgWatt` instead as the effective power measurement while validating the
combined profiles.

| Combination | Expected behavior | Operational guidance |
|---|---|---|
| Low power + `cool` | Lowest temperatures; passive trips may reduce throughput early. | Suitable for fanless or tightly enclosed systems. |
| Balanced power + `warm` | Normal balance of throughput, acoustics, and temperature. | Good starting point for qualification. |
| High power + `hot` or `thermal-max` | More performance until higher temperatures; greater throttle and enclosure risk. | Validate under the real workload before deployment. |
| Any power + thermal trip reached | `Processor` or `intel_powerclamp` reduces performance to hold temperature. | Lower the power target or choose earlier trips when sustained. |

### Supported Profile Combinations

All named profiles can be combined. Each entry gives the operating posture,
not a guarantee that the enclosure can sustain the selected power target.
Validate high-power combinations under the intended workload.

| Power profile | `cool` (55/70/80 C) | `warm` (60/75/85 C) | `hot` (70/90/95 C) | `thermal-max` (95/100/104 C) |
|---|---|---|---|---|
| `LowPower` (10 W) | Maximum thermal margin. | Balanced low-power operation. | Normally little thermal intervention. | Least protective and seldom needed. |
| `BalancedLow` (15 W) | Favors temperature over throughput. | General low-power default. | Permits higher package temperature. | Validate the enclosure before use. |
| `BalancedHigh` (20 W) | May reach passive trips under load. | Recommended starting point. | Higher temperature and throttle risk. | Qualification required. |
| `Performance` (25 W) | Thermal policy can reduce sustained throughput. | Validate sustained workloads. | Increased heat and fan demand. | High-risk for constrained enclosures. |
| `MaxPerformance` (cTDP Level 2) | Thermal trips commonly limit effective throughput. | Require enclosure qualification. | High thermal and throttle risk. | Use only after thermal qualification. |
| `Custom` | Valid explicit targets and trips; apply power first, then regenerate thermal. | Valid explicit targets and trips; apply power first, then regenerate thermal. | Valid explicit targets and trips; apply power first, then regenerate thermal. | Valid explicit targets and trips; apply power first, then regenerate thermal. |

### Conflict and Override Policies

| Condition | Effective policy | Required action |
|---|---|---|
| Power profile is applied before thermal profile | The thermal PPCC maximum is refreshed with the current RAPL PL1. | This is the required order. |
| Thermal profile is applied before, or restarted after, a power-profile change | thermald can restore the older PPCC package cap, overriding the newly intended RAPL PL1. | Re-apply the power profile, then re-apply the thermal profile. |
| A `Processor` or `intel_powerclamp` trip is active | The thermal policy takes precedence for safety and reduces frequency or injects idle cycles; effective power and performance can fall below PL1. | Lower the power profile or select earlier trips if sustained throttling is unacceptable. |
| Requested PL1 or PL2 exceeds the firmware cTDP limit | Firmware clamps the RAPL request; the lower enforced limit wins. | Adjust BIOS cTDP configuration or use the reported effective limit. |
| `--sysWatt` is supplied but psys is unsupported | The SysWatt request is ignored; only PkgWatt is capped. | Track PkgWatt and plan to the package-power limit. |
| SysWatt reads `0.00` on a psys-capable platform | The psys counter may be frozen even though a cap was written. | Use PkgWatt as the observable power measurement. |
| OS restart | RAPL PL1/PL2 reset to firmware defaults while thermald PPCC remains on disk. | Re-apply power first, then thermal, before the next workload. |

## Prerequisites

- Intel `x86_64` host, `msr-tools`, the `msr` kernel module, and `thermald`.
- BIOS permits OS control of package power limits and has the package power
  limit MSR unlocked. See the [Power Profiles User Guide](power-profiles.md).
- `Fan`, `Processor`, or `intel_powerclamp` cooling devices are available:

  ```bash
  grep . /sys/class/thermal/cooling_device*/type
  ```

- Before the first change, preserve any local configuration that is not already
  backed up. The thermal tool's `.bak` files are replaced on each later apply.

  ```bash
  sudo cp -a /etc/thermald/thermal-conf.xml /etc/thermald/thermal-conf.xml.before-power-thermal
  sudo cp -a /etc/systemd/system/thermald.service.d/override.conf /etc/systemd/system/thermald.service.d/override.conf.before-power-thermal
  ```

  If either source file does not exist, record that fact instead of creating an
  empty replacement. The power tool creates a one-time `.orig` backup only for
  model-specific `intel_lpmd` configuration files that it replaces.

## Enable Both Profiles

Preview each profile first. The following uses a 20 W power ceiling and the
`warm` thermal policy:

```bash
tools/power-tuning/set_power_profile.sh --profile BalancedHigh --dry-run
tools/power-tuning/set_thermal_profile.sh --profile warm --dry-run
```

Apply in the required order:

```bash
sudo tools/power-tuning/set_power_profile.sh --profile BalancedHigh
sudo tools/power-tuning/set_thermal_profile.sh --profile warm
```

For a custom package target, apply it before generating the thermal policy so
the PPCC maximum captures the intended PL1:

```bash
sudo tools/power-tuning/set_power_profile.sh --profile Custom --pkgWatt 30 --sysWatt 35 --burstRatio 1.2
sudo tools/power-tuning/set_thermal_profile.sh --profile custom --fan 60 --proc 75 --clamp 85
```

Confirm the effective state:

```bash
systemctl is-active intel_lpmd.service
systemctl is-active thermald
systemctl show thermald -p ExecStart
cat /sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw
```

The thermald command must contain `--ignore-default-control` and must not
contain `--adaptive`. The RAPL value is in microwatts; compare it with the
requested PL1 after allowing for any firmware cTDP clamp reported by the power
script.

## Validate Under Load

Start the monitor before the workload so it captures the ramp, then run a
bounded test in a second terminal. Stop the monitor with `Ctrl-C` after the
stress command completes:

```bash
sudo tools/power-tuning/pt_mon.sh
sudo tools/power-tuning/stress_gen.sh --gpu 12 --duration 3m
```
> **Note:** Use `stress_gen.sh`, `openvino_stress.sh`, an magic9 benchmark, or
> your production workload to generate load for power and thermal profiling.
> Choose a bounded run and use the same workload when comparing profiles.

Watch `PkgTmp` against the thermal trip points and `PkgWatt` against the power
target. `SysWatt=0.00` can mean the psys counter is absent or frozen; use
`PkgWatt` for the effective measurement in that case.

For an orchestrated apply, monitor, stress, and report pass, use the
`combined-power-thermal-profiling` skill. It enforces the same power-then-
thermal sequence.

## Restart Lifecycle

The two tools manage state with different lifetimes:

| State | Location | After OS restart | Required action |
|---|---|---|---|
| Package and psys RAPL PL1/PL2 caps | CPU MSRs and powercap state | Reset to firmware defaults. | Re-apply the intended power profile. |
| `intel_lpmd` tuning | `intel_lpmd` configuration files | Retained and read by `intel_lpmd` at boot. | No action for retention; restore the original configuration to remove it. |
| Thermal trip points and PPCC maximum | `/etc/thermald/thermal-conf.xml` | Retained and read when thermald starts. | Re-apply the thermal profile after the power profile to refresh PPCC with the new live PL1. |
| thermald sole-authority setting | `/etc/systemd/system/thermald.service.d/override.conf` | Retained. | No action unless restoring the packaged thermald behavior. |
| Monitoring and stress processes | Runtime processes and log file | Processes stop; log file remains. | Start a new monitor/test only when needed. |

After **every OS restart**, re-apply the chosen profiles in this exact order:

```bash
sudo tools/power-tuning/set_power_profile.sh --profile BalancedHigh
sudo tools/power-tuning/set_thermal_profile.sh --profile warm
```

Do this even though the `intel_lpmd` and thermald files persist: the rebooted
RAPL cap is volatile, and the thermal profile must be regenerated after the
new cap is live. Re-run the second command after any future power-profile
change or thermald restart that needs to use the new cap.

## Restore Original Settings

To stop using custom thermal control immediately, return thermald to kernel
default thermal control:

```bash
sudo tools/power-tuning/set_thermal_profile.sh --disable
```

To restore the previous thermal files captured by the tool's most recent
apply, copy its backups back and restart thermald:

```bash
sudo cp -a /etc/thermald/thermal-conf.xml.bak /etc/thermald/thermal-conf.xml
sudo cp -a /etc/systemd/system/thermald.service.d/override.conf.bak /etc/systemd/system/thermald.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl restart thermald
```

Use the `*.before-power-thermal` copies made before the first apply when the
goal is the original local configuration rather than only the previous profile.
If thermald was originally disabled, stop and disable it again after restoring
the files.

RAPL limits return to firmware defaults after a reboot. To restore the
`intel_lpmd` daemon configuration immediately, restore the matching
model-specific `.orig` file that the power tool created, then restart the
daemon. For example:

```bash
sudo cp -a /usr/local/etc/intel_lpmd/intel_lpmd_config_F6_M204.xml.orig /usr/local/etc/intel_lpmd/intel_lpmd_config_F6_M204.xml
sudo systemctl restart intel_lpmd.service
```

The generic `intel_lpmd_config.xml` has no automatic backup when it did not
exist before the first power-profile run. Restore a pre-change copy when one
was captured, or use the platform's known-good package configuration. Do not
delete an existing configuration merely to approximate a reset.

## Related Guides

- [Power Profiles User Guide](power-profiles.md)
- [Thermal Profiles User Guide](thermal-profiles.md)
- [Agent Skills](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/agent-skills.html)