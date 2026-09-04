<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Thermal Profiles User Guide

## Overview

Intel® Core™ Ultra edge nodes let you control **how the platform reacts as its
temperature rises** — when fans spin up, when the CPU frequency is capped, and
when idle cycles are forced in as a hard limit. The Infrastructure software
ships a local tool under `tools/power-tuning/` that configures this policy
through the Linux thermal daemon, `thermald`:

- Apply a ready-made **thermal profile** (`cool`, `warm`, `hot`, `thermal-max`).
- Set an explicit set of **custom trip points** (Fan / Processor / powerclamp).
- Optionally add the **CHRG** (battery charge) cooling device.
- **Disable** thermald to revert to kernel default thermal control.

`set_thermal_profile.sh` generates, validates, applies and verifies a
`/etc/thermald/thermal-conf.xml` with a staged escalation on the CPU package
sensor (`x86_pkg_temp`):

```
Fan (active)  <  Processor (passive)  <  intel_powerclamp (passive)
fans on early    cap CPU frequency       inject idle cycles (hard limit)
```

It then makes thermald the **sole thermal authority** (a systemd drop-in that
runs thermald with `--ignore-default-control` and **without** `--adaptive`, so
firmware DPTF/GDDV adaptive tables do not override the trip points).

> **On the target system:** the commands below use repository-relative paths
> (`tools/power-tuning/…`), which work when you run them from the repo root. On a
> host provisioned with Infrastructure software, the same tools are available on
> the target system at `/opt/edge/developer/tools/power-tuning/`. Either
> `cd /opt/edge/developer` and use the relative paths as written, or prefix each
> command with the full path (e.g.
> `sudo /opt/edge/developer/tools/power-tuning/set_thermal_profile.sh --profile warm`).

This thermal profile pairs with the **power envelope** from
[`set_power_profile.sh`](power-profiles.md): the power cap bounds how much heat
is produced, while the thermal profile governs how the platform responds as the
package temperature climbs. Apply the power envelope first, then the thermal
policy.

> **Note:** Unlike the runtime-only RAPL power cap, the thermal config and
> systemd override are written to disk and **persist across a reboot** — see
> [What Persists Across a Reboot](#what-persists-across-a-reboot).

## Prerequisites

- An Intel `x86_64` host (Core Ultra / Panther Lake recommended).
- `thermald` installed (it consumes the generated config and drives the cooling
  devices). Not required for `--dry-run` or `--output` mode:

  ```bash
  sudo apt-get install -y thermald
  ```

- `sudo` access. The script writes to `/etc/thermald/`, installs a systemd
  drop-in, and restarts the service. It does **not** self-elevate, so apply and
  `--disable` runs must be invoked with `sudo`.
- Cooling devices exposed by the kernel. The script wires in whichever of `Fan`,
  `Processor`, `intel_powerclamp` (and `CHRG` when `--charge` is given) are
  present, and refuses to write an empty zone if none exist. Check with:

  ```bash
  grep . /sys/class/thermal/cooling_device*/type
  ```

## Thermal Profiles

A profile is a set of three trip points on the CPU package sensor, ordered
`Fan (active) < Processor (passive) < powerclamp (passive)`. Trip points are in
degrees Celsius.

| Profile | Fan | Processor | powerclamp | Typical use |
|---|---|---|---|---|
| `cool` | 55 | 70 | 80 | Aggressive cooling; fans on early, runs coolest/quietest at the cost of performance |
| `warm` *(default)* | 60 | 75 | 85 | Balanced |
| `hot` | 70 | 90 | 95 | Lets the platform run warmer before intervening |
| `thermal-max` | 95 | 100 | 104 | Pushes to Tjmax headroom; **runs hot** |
| `custom` | `--fan` | `--proc` | `--clamp` | Supply your own trip points |

### Terminology

| Term | Meaning |
|---|---|
| thermald | The Linux thermal daemon that consumes the generated `thermal-conf.xml` and drives the cooling devices. |
| trip point | A temperature threshold at which a cooling action is engaged. |
| active trip | A cooling response that does **not** cost performance — here, turning fans on. |
| passive trip | A cooling response that **reduces performance** to shed heat — frequency capping or idle injection. |
| x86_pkg_temp | The CPU package temperature sensor the profile escalates on. |
| Fan | The active cooling device engaged at the first (lowest) trip. |
| Processor | The passive cooling device that caps CPU frequency at the middle trip. |
| intel_powerclamp | The passive cooling device that injects idle cycles (hard limit) at the top trip. |
| CHRG | The battery-charge cooling device; optionally added to the top trip when present (`--charge`). |
| Tjmax | The silicon's maximum junction temperature (~110 °C); the top trip must stay below it (`< 105`). |
| DPTF / GDDV | Firmware adaptive thermal framework/tables that would override the config unless thermald runs without `--adaptive`. |

## Apply a Named Profile

Use `set_thermal_profile.sh` with `--profile`. The profile must be given via the
flag; a bare positional word is rejected. Run from the repository root:

```bash
# Balanced (default) — Fan 60 / Processor 75 / powerclamp 85 °C
sudo tools/power-tuning/set_thermal_profile.sh --profile warm

# Aggressive cooling — fans on early, coolest/quietest
sudo tools/power-tuning/set_thermal_profile.sh --profile cool

# Run warmer before intervening
sudo tools/power-tuning/set_thermal_profile.sh --profile hot

# Push to Tjmax headroom — runs hot; warn on fanless/constrained enclosures
sudo tools/power-tuning/set_thermal_profile.sh --profile thermal-max

# Add the battery-charge (CHRG) cooling device to the top trip, if present
sudo tools/power-tuning/set_thermal_profile.sh --profile cool --charge

# Preview only — print the plan and generated XML without changing anything
tools/power-tuning/set_thermal_profile.sh --profile warm --dry-run
```

## Set Custom Trip Points

For fine-grained control, supply your own three trip points instead of a named
profile. All three are required and must satisfy `fan < proc < clamp` with
`clamp < 105` (must stay below Tjmax).

```bash
# Custom escalation — Fan 50 / Processor 65 / powerclamp 78 °C
sudo tools/power-tuning/set_thermal_profile.sh --profile custom \
  --fan 50 --proc 65 --clamp 78

# Preview a custom profile without applying it
tools/power-tuning/set_thermal_profile.sh --profile custom \
  --fan 50 --proc 65 --clamp 78 --dry-run
```

| Option | Meaning |
|---|---|
| `-p, --profile <name>` | Profile to apply: `cool`, `warm`, `hot`, `thermal-max`, or `custom` (default `warm`). |
| `--fan <C>` | Fan (active) trip in Celsius (custom only). |
| `--proc <C>` | Processor (passive) trip in Celsius (custom only). |
| `--clamp <C>` | powerclamp (passive) trip in Celsius (custom only). |
| `--charge` | Add the CHRG (battery charge) cooling device to the top trip, if present on this platform. |
| `-o, --output <file>` | Write the XML to `<file>` instead of installing it. Implies no daemon changes. |
| `--disable` | Stop thermald and disable it at boot (reverts to kernel default thermal control). |
| `-n, --dry-run` | Print the plan and generated XML; write nothing, change nothing. |

## Generate the XML Without Applying It

To produce the `thermal-conf.xml` for review or use elsewhere without touching
the running daemon, write it to a file with `-o/--output`:

```bash
sudo tools/power-tuning/set_thermal_profile.sh --profile warm -o /tmp/thermal-conf.xml
```

This writes only the XML and makes **no** daemon changes.

## Disable Thermald (Revert to Kernel Default)

To fully revert to kernel default thermal control, disable thermald. This stops
the service and disables it at boot, leaving the config and override files
untouched:

```bash
sudo tools/power-tuning/set_thermal_profile.sh --disable
```

Re-enable it later with:

```bash
sudo systemctl enable --now thermald
```

## Verify and Monitor

After applying, confirm thermald is active and is the sole thermal authority
(the effective `ExecStart` contains `--ignore-default-control` and **not**
`--adaptive`):

```bash
systemctl is-active thermald
systemctl show thermald -p ExecStart
```

To watch the package temperature cross the trip points under load, pair this
with the power-tuning monitor and stress tools (see
[Power Profiles](power-profiles.md#monitor-power-and-temperature)):

```bash
# Terminal 1 — live power/thermal monitor (watch PkgTmp against the trips)
cd tools/power-tuning && sudo ./pt_mon.sh

# Terminal 2 — drive the platform hot enough to exercise the trip points
tools/power-tuning/stress_gen.sh --duration 3m
```

Watch for the escalation stages engaging in order: fans on at the Fan trip,
frequency capping at the Processor trip, and idle injection at the powerclamp
trip.

## Side Effects and Tips

- **`thermal-max` runs hot:** its top trip sits near Tjmax, so the platform
  intervenes only very late. On fanless / thermally constrained enclosures this
  can mean sustained high temperatures — prefer `cool` or `warm` there.
- **Fanless platforms:** if no `Fan` cooling device exists, the active step is
  omitted and the platform relies solely on the passive steps (frequency cap +
  idle injection).
- **Sole thermal authority:** the systemd override runs thermald **without**
  `--adaptive` so firmware DPTF/GDDV adaptive tables cannot override the trip
  points. If the profile seems ignored, confirm the effective `ExecStart` still
  has `--ignore-default-control` and no `--adaptive`.
- **Config is validated first:** the script parses the generated XML in
  thermald test-mode before installing it and aborts without changing the system
  if it does not validate.
- **Brief management gap:** applying a profile restarts `thermald`; if the
  script aborts mid-run it restores the previously running daemon.

## What Persists Across a Reboot

Unlike the runtime-only RAPL power cap from
[`set_power_profile.sh`](power-profiles.md#what-persists-across-a-reboot), the
thermal config and systemd override are written to disk and **persist across a
reboot**:

| What changes | Where it lives | Reverts on reboot? |
|---|---|---|
| Thermal trip points | `/etc/thermald/thermal-conf.xml` | **No** — thermald re-reads it at the next boot. |
| Sole-authority `ExecStart` | `/etc/systemd/system/thermald.service.d/override.conf` | **No** — the drop-in stays on disk. |

To change the trip points, simply re-run with a different `--profile` (the script
backs up the previous config to `${CONF_FILE}.bak` and the override to
`${OVERRIDE_FILE}.bak`). To restore the previous config manually:

```bash
sudo cp /etc/thermald/thermal-conf.xml.bak /etc/thermald/thermal-conf.xml
sudo systemctl restart thermald
```

To fully revert to kernel default thermal control, run with `--disable` (see
[Disable Thermald](#disable-thermald-revert-to-kernel-default)).

## Related Agent Skills

The same tool is also driven by an agent skill (see
[AI Agent Integration](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/agent-skills.html)):

| Skill | Purpose |
|---|---|
| `set-thermal-profile` | Generate, apply and verify a thermald thermal profile (or disable thermald). |
| `set-power-profile` | Cap the package/platform power so less heat is produced (apply first). |
| `monitor-power-thermal` | Watch PkgTmp against the trip points while a load runs. |
| `generate-platform-stress` | Drive the platform hot enough to exercise the trip points. |

**Typical loop:** set a power profile → set this thermal profile → start
`monitor-power-thermal` → run `generate-platform-stress` with a bounded
duration → confirm the temperature holds within the trips without unexpected
throttling.

These skills run **directly on the target host** — they write `/etc/thermald/`
and restart a system service, which must happen locally on the node. To drive
them by natural language on a provisioned node, install an agent CLI on the
target host and open it in the developer source tree (`/opt/edge/developer`),
where the `skills/` directory and `tools/power-tuning/` scripts already live.
See [Power Profiles](power-profiles.md#install-the-claude-code-cli-on-the-target-host-ubuntu)
for the agent-CLI install steps.
