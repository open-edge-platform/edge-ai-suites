#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Write xe-compatible GPU telemetry snapshots from xpu-smi to JSON."""

from __future__ import annotations

import argparse
import csv
import ctypes
import glob
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> str:
  proc = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=10)
  return proc.stdout


def _run_optional(cmd: list[str]) -> str | None:
  try:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=10)
  except OSError:
    return None
  if proc.returncode != 0:
    return None
  return proc.stdout


def _read_text_optional(path: Path) -> str | None:
  try:
    return path.read_text(encoding="utf-8").strip()
  except OSError:
    pass

  sudo = shutil.which("sudo")
  if not sudo or os.geteuid() == 0:
    return None

  output = _run_optional([sudo, "-n", "cat", str(path)])
  if output is None:
    return None
  return output.strip()


def _resolve_gpu_name(gpu: dict) -> str:
  pci_bdf = gpu.get("pci_bdf_address")
  raw_name = gpu.get("device_name") or f"Intel GPU ({pci_bdf or 'unknown'})"
  if not pci_bdf:
    return raw_name

  lspci = shutil.which("lspci")
  if not lspci:
    return raw_name

  output = _run_optional([lspci, "-D", "-s", pci_bdf, "-nn"])
  if not output:
    return raw_name

  text = output.strip()
  if not text:
    return raw_name

  description = text.split(": ", 1)[-1]
  for prefix in (
    "VGA compatible controller ",
    "Display controller ",
    "3D controller ",
  ):
    if description.startswith(prefix):
      description = description[len(prefix):]
      break

  description = re.sub(r"\s*\[[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\]", "", description)
  description = re.sub(r"\s*\(rev\s+[0-9a-fA-F]+\)$", "", description).strip()
  return description or raw_name


def _detect_intel_gpu_card() -> str | None:
  for vendor_file in sorted(Path("/sys/class/drm").glob("card*/device/vendor")):
    try:
      vendor = vendor_file.read_text(encoding="utf-8").strip()
    except OSError:
      continue
    if vendor != "0x8086":
      continue
    return vendor_file.parents[1].name
  return None


def _detect_gpu_driver(card: str | None) -> str | None:
  if not card:
    return None
  driver_link = Path(f"/sys/class/drm/{card}/device/driver")
  try:
    return driver_link.resolve().name
  except OSError:
    return None


def _resolve_gpu_name_from_card(card: str | None) -> str:
  if not card:
    return "Intel GPU"
  device_link = Path(f"/sys/class/drm/{card}/device")
  try:
    pci_bdf = device_link.resolve().name
  except OSError:
    return f"Intel GPU ({card})"

  lspci = shutil.which("lspci")
  if not lspci:
    return f"Intel GPU ({card})"

  output = _run_optional([lspci, "-D", "-s", pci_bdf, "-nn"])
  if not output:
    return f"Intel GPU ({card})"

  description = output.strip().split(": ", 1)[-1]
  for prefix in (
    "VGA compatible controller ",
    "Display controller ",
    "3D controller ",
  ):
    if description.startswith(prefix):
      description = description[len(prefix):]
      break
  description = re.sub(r"\s*\[[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\]", "", description)
  description = re.sub(r"\s*\(rev\s+[0-9a-fA-F]+\)$", "", description).strip()
  return description or f"Intel GPU ({card})"


def _discover_device(device: str | None) -> dict:
  payload = json.loads(_run(["xpu-smi", "discovery", "-j"]))
  devices = payload.get("device_list") or []
  if not devices:
    raise RuntimeError("xpu-smi did not report any GPU devices")
  if device is None:
    return devices[0]
  for candidate in devices:
    if str(candidate.get("device_id")) == device or candidate.get("pci_bdf_address") == device:
      return candidate
  raise RuntimeError(f"xpu-smi device not found: {device}")


def _gpu_percent(device_id: str) -> float | None:
  output = _run(["xpu-smi", "dump", "-d", device_id, "-m", "0", "-i", "1", "-n", "1"])
  rows = list(csv.DictReader(io.StringIO(output)))
  if not rows:
    return None
  row = rows[-1]
  for key, value in row.items():
    if "GPU Utilization" not in key and "utilization of all GPU Engines" not in key:
      continue
    value = value.strip()
    if not value or value.upper() == "N/A":
      return None
    return round(float(value), 1)
  return None


def _stats_percent(device_id: str, use_sudo: bool = False) -> float | None:
  cmd = ["xpu-smi", "stats", "-d", device_id, "-j"]
  if use_sudo:
    cmd = ["sudo", "-n", *cmd]
  output = _run_optional(cmd)
  if not output:
    return None
  try:
    payload = json.loads(output)
  except json.JSONDecodeError:
    return None

  metrics = {
    entry.get("metrics_type"): entry.get("value")
    for entry in payload.get("device_level") or []
    if isinstance(entry, dict)
  }
  for key in (
    "XPUM_STATS_GPU_UTILIZATION",
    "XPUM_STATS_ENGINE_GROUP_COMPUTE_ALL_UTILIZATION",
    "XPUM_STATS_ENGINE_GROUP_RENDER_ALL_UTILIZATION",
    "XPUM_STATS_ENGINE_GROUP_COPY_ALL_UTILIZATION",
  ):
    value = metrics.get(key)
    if isinstance(value, (int, float)):
      return round(float(value), 1)

  for engines in (payload.get("engine_util") or {}).values():
    if not isinstance(engines, list):
      continue
    numeric = [engine.get("value") for engine in engines if isinstance(engine, dict) and isinstance(engine.get("value"), (int, float))]
    if numeric:
      return round(max(float(value) for value in numeric), 1)
  return None


def _stats_power(device_id: str, use_sudo: bool = False) -> float | None:
  cmd = ["xpu-smi", "stats", "-d", device_id, "-j"]
  if use_sudo:
    cmd = ["sudo", "-n", *cmd]
  output = _run_optional(cmd)
  if not output:
    return None
  try:
    payload = json.loads(output)
  except json.JSONDecodeError:
    return None

  metrics = {
    entry.get("metrics_type"): entry.get("value")
    for entry in payload.get("device_level") or []
    if isinstance(entry, dict)
  }
  for key in (
    "XPUM_STATS_POWER",
    "XPUM_STATS_POWER_USAGE",
    "XPUM_STATS_GPU_POWER",
  ):
    value = metrics.get(key)
    if isinstance(value, (int, float)):
      return round(float(value), 1)
  return None


def _cpu_package_power() -> float | None:
  package_paths = set(Path("/sys/class/powercap").glob("intel-rapl:*"))
  nested_root = Path("/sys/class/powercap/intel-rapl")
  if nested_root.exists():
    package_paths.update(nested_root.glob("intel-rapl:*"))
  package_paths = sorted(package_paths)
  if not package_paths:
    return None

  watts = []
  for package_path in package_paths:
    name = _read_text_optional(package_path / "name")
    if not name:
      continue
    if not name.startswith("package-"):
      continue

    power_uw = _read_text_optional(package_path / "power_uw")
    if not power_uw:
      continue
    try:
      watts.append(float(power_uw) / 1_000_000.0)
    except ValueError:
      continue

  if not watts:
    return None
  return round(sum(watts), 1)


def _turbostat_sample(use_sudo: bool = False) -> dict[str, float] | None:
  turbostat = shutil.which("turbostat")
  if not turbostat:
    return None

  cmd = [
    turbostat,
    "--Summary",
    "--quiet",
    "--show",
    "PkgTmp,PkgWatt,GFXWatt",
    "-i",
    "0.5",
    "-n",
    "1",
  ]
  if use_sudo:
    cmd = ["sudo", "-n", *cmd]

  output = _run_optional(cmd)
  if not output:
    return None

  lines = [line.strip() for line in output.splitlines() if line.strip()]
  if len(lines) < 2:
    return None

  headers = re.split(r"\s+", lines[-2])
  values = re.split(r"\s+", lines[-1])
  if len(headers) != len(values):
    return None

  parsed: dict[str, float] = {}
  for key, value in zip(headers, values):
    try:
      parsed[key] = float(value)
    except ValueError:
      continue
  return parsed or None


def _cpu_package_power_from_turbostat() -> float | None:
  sample = _turbostat_sample()
  if sample is None and shutil.which("sudo") and os.geteuid() != 0:
    sample = _turbostat_sample(use_sudo=True)
  if sample is None:
    return None

  value = sample.get("PkgWatt")
  if value is None:
    return None
  return round(float(value), 1)


def _xe_gtidle_percent(card: str | None, sample_s: float = 0.25) -> float | None:
  if not card:
    return None
  paths = sorted(glob.glob(f"/sys/class/drm/{card}/device/tile*/gt*/gtidle/idle_residency_ms"))
  if not paths:
    return None

  before = []
  for path in paths:
    value = _read_text_optional(Path(path))
    if value is None:
      return None
    try:
      before.append(int(value))
    except ValueError:
      return None

  start = time.monotonic()
  time.sleep(sample_s)
  after = []
  for path in paths:
    value = _read_text_optional(Path(path))
    if value is None:
      return None
    try:
      after.append(int(value))
    except ValueError:
      return None
  elapsed_ms = (time.monotonic() - start) * 1000.0 * len(paths)
  if elapsed_ms <= 0:
    return None

  delta_idle = sum(max(0, a - b) for a, b in zip(after, before))
  busy_frac = max(0.0, min(1.0, 1.0 - delta_idle / elapsed_ms))
  return round(busy_frac * 100.0, 1)


# ── i915 PMU (kernel hardware engine-busy counters) ─────────────────────────
# These counters are exposed by the kernel regardless of whether the userspace
# xpu-smi dump metrics are supported.  They require perf_event_paranoid <= 0
# (set in setup.sh via sysctl) or CAP_PERFMON.
#
# The xe driver on Arrow Lake / Meteor Lake registers its PMU under the "i915"
# name via a compatibility shim in the kernel, so the same event source works
# for both i915 and xe driver systems.

_PERF_FORMAT_TOTAL_TIME_ENABLED = 1 << 1
_PERF_FLAG_FD_CLOEXEC = 8
_SYS_PERF_EVENT_OPEN = 298  # x86_64 only


class _PerfEventAttr(ctypes.Structure):
  _fields_ = [
    ("type",               ctypes.c_uint32),
    ("size",               ctypes.c_uint32),
    ("config",             ctypes.c_uint64),
    ("sample_period",      ctypes.c_uint64),
    ("sample_type",        ctypes.c_uint64),
    ("read_format",        ctypes.c_uint64),
    ("flags",              ctypes.c_uint64),
    ("wakeup_events",      ctypes.c_uint32),
    ("bp_type",            ctypes.c_uint32),
    ("config1",            ctypes.c_uint64),
    ("config2",            ctypes.c_uint64),
    ("branch_sample_type", ctypes.c_uint64),
    ("sample_regs_user",   ctypes.c_uint64),
    ("sample_stack_user",  ctypes.c_uint32),
    ("clockid",            ctypes.c_int32),
    ("sample_regs_intr",   ctypes.c_uint64),
    ("aux_watermark",      ctypes.c_uint32),
    ("sample_max_stack",   ctypes.c_uint16),
    ("__reserved",         ctypes.c_uint16),
    ("aux_sample_size",    ctypes.c_uint32),
    ("__reserved2",        ctypes.c_uint32),
  ]


def _i915_pmu_percent(sample_s: float = 0.25) -> float | None:
  """Return the max engine busy % across render/compute/video engines
  by reading the i915 PMU hardware counters directly.

  Returns None if the PMU is unavailable or perf_event_paranoid is too
  restrictive.  sample_s controls the measurement window in seconds.
  """
  pmu_base = Path("/sys/bus/event_source/devices/i915")
  type_file = pmu_base / "type"
  cpumask_file = pmu_base / "cpumask"
  if not type_file.exists():
    return None
  try:
    pmu_type = int(type_file.read_text().strip())
    cpu = int(cpumask_file.read_text().strip().split(",")[0])
  except (OSError, ValueError):
    return None

  engine_events = ["rcs0-busy", "ccs0-busy", "vcs0-busy"]
  configs: list[tuple[str, int]] = []
  for ev in engine_events:
    ev_file = pmu_base / "events" / ev
    if not ev_file.exists():
      continue
    try:
      line = ev_file.read_text().strip()
      cfg = int(line.split("=")[1], 16)
      configs.append((ev, cfg))
    except (OSError, ValueError, IndexError):
      continue
  if not configs:
    return None

  libc = ctypes.CDLL("libc.so.6", use_errno=True)
  fds: list[int] = []
  try:
    for _name, cfg in configs:
      attr = _PerfEventAttr()
      attr.type        = pmu_type
      attr.size        = ctypes.sizeof(_PerfEventAttr)
      attr.config      = cfg
      attr.read_format = _PERF_FORMAT_TOTAL_TIME_ENABLED
      fd = libc.syscall(
        _SYS_PERF_EVENT_OPEN,
        ctypes.byref(attr),
        -1, cpu, -1,
        _PERF_FLAG_FD_CLOEXEC,
      )
      if fd < 0:
        return None
      fds.append(fd)

    def _read_all() -> list[tuple[int, int]]:
      return [struct.unpack("QQ", os.read(fd, 16)) for fd in fds]

    before = _read_all()
    time.sleep(sample_s)
    after = _read_all()
  finally:
    for fd in fds:
      try:
        os.close(fd)
      except OSError:
        pass

  best: float | None = None
  for (v0, e0), (v1, e1) in zip(before, after):
    delta_e = e1 - e0
    if delta_e <= 0:
      continue
    # Clamp to 100%: on xe2, the xe→i915 PMU shim aggregates multiple
    # internal sub-engines (e.g. several CCS slices) into one counter, so
    # raw busy_ns can legitimately exceed time_enabled_ns.  Clamping gives
    # the semantics "any engine class fully saturated → 100%".
    pct = min(100.0, round(100.0 * (v1 - v0) / delta_e, 1))
    if best is None or pct > best:
      best = pct
  return best


def _xe_freq_mhz(drm_device: str) -> tuple[int, int] | None:
  """Return (cur_freq_mhz, max_freq_mhz) from sysfs for the xe driver.

  Used only to surface informational frequency data in the status string when
  xpu-smi cannot report a real GPU utilization percentage (Arrow Lake and
  other xe-driver platforms).  Frequency is not reported as a utilization
  percentage because the xe driver routinely pins the GPU at max clock
  regardless of actual engine load, making the ratio uninformative.
  """
  card = Path(drm_device).name  # e.g. "card1" from "/dev/dri/card1"
  base = Path(f"/sys/class/drm/{card}/gt/gt0")
  try:
    cur = int((base / "rps_cur_freq_mhz").read_text().strip())
    mx  = int((base / "rps_max_freq_mhz").read_text().strip())
    return cur, mx
  except (OSError, ValueError):
    return None


def collect(device: str | None) -> dict:
  tool = shutil.which("xpu-smi")
  cpu_watts = _cpu_package_power()
  if cpu_watts is None:
    cpu_watts = _cpu_package_power_from_turbostat()

  if not tool:
    card = _detect_intel_gpu_card()
    driver = _detect_gpu_driver(card)
    percent = _xe_gtidle_percent(card) if driver == "xe" else None
    return {
      "timestamp": time.time(),
      "name": _resolve_gpu_name_from_card(card),
      "percent": percent,
      "power_watts": None,
      "cpu_watts": cpu_watts,
      "status": "ok" if percent is not None else "cpu-only telemetry",
      "source": "xe gtidle+turbostat" if percent is not None and cpu_watts is not None else ("xe gtidle" if percent is not None else ("turbostat" if cpu_watts is not None else "unavailable")),
    }
  gpu = _discover_device(device)
  device_id = str(gpu["device_id"])
  percent = _gpu_percent(device_id)
  power_watts = None
  source = "xpu-smi dump"
  if percent is None and shutil.which("sudo") and os.geteuid() != 0:
    percent = _stats_percent(device_id, use_sudo=True)
    if percent is not None:
      source = "xpu-smi stats (sudo)"
  if percent is None:
    percent = _stats_percent(device_id)
    if percent is not None:
      source = "xpu-smi stats"

  if shutil.which("sudo") and os.geteuid() != 0:
    power_watts = _stats_power(device_id, use_sudo=True)
  if power_watts is None:
    power_watts = _stats_power(device_id)

  # xpu-smi metrics unavailable or unreliable (xe driver on Arrow Lake and
  # similar): try the kernel i915 PMU hardware engine-busy counters, which
  # give accurate per-engine utilization without needing any Intel tools.
  # Also override a zero reading from xpu-smi stats since Arrow Lake returns
  # zero for XPUM_STATS_GPU_UTILIZATION even under active inference load.
  if percent is None or percent == 0.0:
    pmu_pct = _i915_pmu_percent()
    if pmu_pct is not None:
      percent = pmu_pct
      source = "i915 PMU"

  # Last resort: include the GPU frequency in the status string so the
  # dashboard shows something useful rather than a blank "unavailable".
  if percent is None:
    drm_device = gpu.get("drm_device", "")
    freq = _xe_freq_mhz(drm_device) if drm_device else None
    if freq is not None:
      cur_mhz, max_mhz = freq
      status = f"xe: {cur_mhz} MHz (max {max_mhz} MHz; utilization N/A)"
    else:
      status = "utilization unavailable"
  else:
    status = "ok"

  return {
    "timestamp": time.time(),
    # Prefer the host's PCI-resolved name because xpu-smi discovery can lag
    # behind refreshed pci.ids mappings on newer Panther Lake devices.
    "name": _resolve_gpu_name(gpu),
    "percent": percent,
    "power_watts": power_watts,
    "cpu_watts": cpu_watts,
    "status": status,
    "source": source,
    "device_id": gpu.get("device_id"),
    "pci_bdf_address": gpu.get("pci_bdf_address"),
  }


def _write_json(path: Path, payload: dict) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  tmp = path.with_suffix(path.suffix + ".tmp")
  tmp.write_text(json.dumps(payload), encoding="utf-8")
  tmp.replace(path)


def main() -> int:
  parser = argparse.ArgumentParser(description="Bridge xpu-smi GPU telemetry into JSON for the dashboard")
  parser.add_argument("--output", default="generated/telemetry/xpu-smi.json")
  parser.add_argument("--device", default=None,
                      help="xpu-smi device id or PCI BDF address; defaults to the first discovered device")
  parser.add_argument("--interval", type=float, default=1.0)
  parser.add_argument("--loop", action="store_true")
  args = parser.parse_args()

  output_path = Path(args.output)
  if not output_path.is_absolute():
    output_path = REPO_ROOT / output_path

  while True:
    try:
      payload = collect(args.device)
    except Exception as exc:
      payload = {
        "timestamp": time.time(),
        "name": "Intel GPU",
        "percent": None,
        "status": str(exc),
        "source": "xpu-smi",
      }
    _write_json(output_path, payload)
    if not args.loop:
      break
    time.sleep(args.interval)

  return 0


if __name__ == "__main__":
  sys.exit(main())