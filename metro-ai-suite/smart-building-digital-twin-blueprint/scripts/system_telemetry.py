#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""System telemetry sampling for dashboard snapshots."""

from __future__ import annotations

import csv
import glob
import io
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)
XPU_SMI_JSON_MAX_AGE_S = 5.0
_BRIDGE_ENSURE_INTERVAL_S = 30.0  # minimum seconds between auto-restart attempts
_RAPL_SAMPLE_MIN_INTERVAL_S = 0.5


def _read_text(path: str) -> str | None:
  try:
    return Path(path).read_text(encoding="utf-8").strip()
  except OSError:
    return None


class SystemTelemetry:
  """Collect best-effort host telemetry visible from the analytics service."""

  def __init__(self, storage_path: str = "/"):
    self._storage_path = storage_path
    self._lock = threading.Lock()
    self._cpu_prev = self._read_cpu_times()
    self._cpu_sku = self._read_cpu_sku()
    self._xpu_smi_json_path = os.environ.get("XPU_SMI_JSON_PATH", "/app/generated/telemetry/xpu-smi.json")
    self._xpu_smi_cmd = shutil.which("xpu-smi")
    self._gpu_card = self._detect_intel_gpu_card()
    self._gpu_driver = self._detect_gpu_driver(self._gpu_card)
    self._gpu_tool = shutil.which("intel_gpu_top")
    self._lspci_cmd = shutil.which("lspci")
    # xe driver gtidle state: (idle_ms, wall_time) sampled on each call
    self._xe_gtidle_prev: tuple[int, float] | None = None
    self._bridge_ensure_script = Path(__file__).parent / "ensure_xpu_smi_bridge.sh"
    self._bridge_last_ensure_ts: float = 0.0
    self._rapl_prev: dict[str, tuple[int, float]] = {}

  def snapshot(self) -> dict:
    with self._lock:
      bridge_payload = self._read_xpu_smi_json_payload()
      cpu = self._cpu_snapshot(bridge_payload)
      gpu = self._gpu_snapshot(bridge_payload)
      temperature = self._temperature_snapshot()
      return {
        "cpu_sku": self._cpu_sku,
        "cpu": cpu,
        "gpu": gpu,
        "temperature": temperature,
        "memory": self._memory_snapshot(),
        "storage": self._storage_snapshot(),
        "power": self._power_snapshot(cpu, gpu, bridge_payload, temperature),
      }

  @staticmethod
  def _read_cpu_sku() -> str:
    try:
      with open("/proc/cpuinfo", encoding="utf-8") as fh:
        for line in fh:
          if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    except OSError:
      pass
    return "Unknown CPU"

  @staticmethod
  def _read_cpu_times() -> tuple[int, int] | None:
    try:
      with open("/proc/stat", encoding="utf-8") as fh:
        fields = fh.readline().split()[1:]
    except OSError:
      return None
    if len(fields) < 8:
      return None
    values = [int(value) for value in fields]
    idle = values[3] + values[4]
    total = sum(values)
    return total, idle

  def _cpu_snapshot(self, bridge_payload: dict | None = None) -> dict:
    current = self._read_cpu_times()
    percent = None
    if current and self._cpu_prev:
      total_delta = current[0] - self._cpu_prev[0]
      idle_delta = current[1] - self._cpu_prev[1]
      if total_delta > 0:
        percent = round(max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta))), 1)
    self._cpu_prev = current
    power_watts = self._cpu_power_from_bridge(bridge_payload)
    if power_watts is None:
      power_watts = self._cpu_power_from_rapl()
    return {"percent": percent, "power_watts": power_watts}

  @staticmethod
  def _memory_snapshot() -> dict:
    meminfo: dict[str, int] = {}
    try:
      with open("/proc/meminfo", encoding="utf-8") as fh:
        for line in fh:
          key, value = line.split(":", 1)
          meminfo[key] = int(value.strip().split()[0]) * 1024
    except OSError:
      return {"total_bytes": None, "used_bytes": None, "percent": None}

    total = meminfo.get("MemTotal")
    available = meminfo.get("MemAvailable")
    if not total or available is None:
      return {"total_bytes": total, "used_bytes": None, "percent": None}

    used = max(total - available, 0)
    percent = round((used / total) * 100.0, 1) if total else None
    return {"total_bytes": total, "used_bytes": used, "percent": percent}

  def _storage_snapshot(self) -> dict:
    try:
      stats = os.statvfs(self._storage_path)
    except OSError:
      return {
        "path": self._storage_path,
        "total_bytes": None,
        "used_bytes": None,
        "percent": None,
      }

    total = stats.f_blocks * stats.f_frsize
    free = stats.f_bavail * stats.f_frsize
    used = max(total - free, 0)
    percent = round((used / total) * 100.0, 1) if total else None
    return {
      "path": self._storage_path,
      "total_bytes": total,
      "used_bytes": used,
      "percent": percent,
    }

  def _temperature_snapshot(self) -> dict:
    return {
      "package_c": self._read_cpu_package_temp_c(),
    }

  @staticmethod
  def _read_temp_c(path: str) -> float | None:
    value = _read_text(path)
    if value is None:
      return None
    try:
      temp_c = float(value)
    except ValueError:
      return None
    if temp_c > 1000.0:
      temp_c /= 1000.0
    return round(temp_c, 1)

  def _read_cpu_package_temp_c(self) -> float | None:
    coretemp = self._read_hwmon_temp_c("coretemp", preferred_label="Package id 0")
    if coretemp is not None:
      return coretemp

    for zone in sorted(glob.glob("/sys/class/thermal/thermal_zone*")):
      zone_path = Path(zone)
      zone_type = _read_text(str(zone_path / "type")) or ""
      if zone_type == "x86_pkg_temp":
        return self._read_temp_c(str(zone_path / "temp"))
    return None

  def _read_hwmon_temp_c(self, hwmon_name: str, preferred_label: str | None = None) -> float | None:
    for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
      hwmon_path = Path(hwmon)
      name = _read_text(str(hwmon_path / "name"))
      if name != hwmon_name:
        continue

      labeled_values: list[tuple[str, float]] = []
      fallback_values: list[float] = []
      for temp_input in sorted(hwmon_path.glob("temp*_input")):
        temp_c = self._read_temp_c(str(temp_input))
        if temp_c is None:
          continue
        fallback_values.append(temp_c)
        label_path = hwmon_path / temp_input.name.replace("_input", "_label")
        label = _read_text(str(label_path))
        if label:
          labeled_values.append((label, temp_c))

      if preferred_label is not None:
        for label, temp_c in labeled_values:
          if label == preferred_label:
            return temp_c

      if fallback_values:
        return max(fallback_values)
    return None

  @staticmethod
  def _detect_intel_gpu_card() -> str | None:
    for vendor_file in sorted(glob.glob("/sys/class/drm/card*/device/vendor")):
      vendor = _read_text(vendor_file)
      if vendor != "0x8086":
        continue
      return Path(vendor_file).parents[1].name
    return None

  @staticmethod
  def _detect_gpu_driver(card: str | None) -> str | None:
    if not card:
      return None
    driver_link = Path(f"/sys/class/drm/{card}/device/driver")
    try:
      return driver_link.resolve().name
    except OSError:
      return None

  def _gpu_snapshot(self, bridge_payload: dict | None = None) -> dict:
    bridged = self._gpu_snapshot_from_json(bridge_payload)
    if bridged is not None:
      return bridged

    direct_xpu = self._gpu_snapshot_from_xpu_smi()
    if direct_xpu is not None:
      return direct_xpu

    if not self._gpu_card:
      return {
        "name": "Intel GPU",
        "percent": None,
        "power_watts": None,
        "status": "not detected",
      }

    sysfs_percent = self._gpu_percent_from_sysfs()
    if sysfs_percent is not None:
      return {
        "name": self._gpu_card,
        "percent": sysfs_percent,
        "power_watts": self._gpu_power_from_sysfs(),
        "status": "ok",
      }

    xe_percent = self._gpu_percent_from_xe_gtidle()
    if xe_percent is not None:
      return {
        "name": f"Intel GPU ({self._gpu_card})",
        "percent": xe_percent,
        "power_watts": self._gpu_power_from_sysfs(),
        "status": "ok",
      }

    top_percent = self._gpu_percent_from_intel_gpu_top()
    if top_percent is not None:
      return {
        "name": f"Intel GPU ({self._gpu_card})",
        "percent": top_percent,
        "power_watts": self._gpu_power_from_sysfs(),
        "status": "ok",
      }

    if self._gpu_driver == "xe" and self._gpu_tool:
      reason = "xe driver not supported by intel_gpu_top"
    else:
      reason = "intel_gpu_top unavailable" if not self._gpu_tool else "usage unavailable"
    return {
      "name": f"Intel GPU ({self._gpu_card})",
      "percent": None,
      "power_watts": self._gpu_power_from_sysfs(),
      "status": reason,
    }

  def _power_snapshot(
    self,
    cpu: dict,
    gpu: dict,
    bridge_payload: dict | None = None,
    temperature: dict | None = None,
  ) -> dict:
    cpu_watts = self._cpu_power_from_bridge(bridge_payload)
    if cpu_watts is None:
      cpu_watts = self._cpu_power_from_rapl()

    gpu_watts = self._gpu_power_from_bridge(bridge_payload)
    if gpu_watts is None:
      gpu_watts = self._gpu_power_from_xpu_smi()
    if gpu_watts is None:
      gpu_watts = self._gpu_power_from_sysfs()

    direct_watts = None
    direct_sources = []
    if cpu_watts is not None:
      direct_sources.append("cpu")
    if gpu_watts is not None:
      direct_sources.append("gpu")
    if direct_sources:
      direct_watts = round((cpu_watts or 0.0) + (gpu_watts or 0.0), 1)

    if direct_watts is not None:
      return {
        "package_watts": direct_watts,
        "is_estimated": False,
        "source": "+".join(direct_sources),
      }

    estimated_watts = self._estimate_package_power(
      cpu_percent=cpu.get("percent"),
      gpu_percent=gpu.get("percent"),
      package_temp_c=(temperature or {}).get("package_c"),
    )
    return {
      "package_watts": estimated_watts,
      "is_estimated": estimated_watts is not None,
      "source": "utilization-heuristic" if estimated_watts is not None else "unavailable",
    }

  @staticmethod
  def _estimate_package_power(
    cpu_percent: float | None,
    gpu_percent: float | None,
    package_temp_c: float | None,
  ) -> float | None:
    if cpu_percent is None and gpu_percent is None and package_temp_c is None:
      return None

    estimate = 3.0
    if isinstance(cpu_percent, (int, float)):
      estimate += max(0.0, min(100.0, float(cpu_percent))) * 0.14
    if isinstance(gpu_percent, (int, float)):
      estimate += max(0.0, min(100.0, float(gpu_percent))) * 0.10
    if isinstance(package_temp_c, (int, float)):
      estimate += max(0.0, float(package_temp_c) - 40.0) * 0.05
    return round(estimate, 1)

  def _ensure_bridge(self) -> None:
    """Trigger ensure_xpu_smi_bridge.sh in the background if not called recently."""
    now = time.time()
    if now - self._bridge_last_ensure_ts < _BRIDGE_ENSURE_INTERVAL_S:
      return
    if not self._bridge_ensure_script.exists():
      return
    self._bridge_last_ensure_ts = now
    try:
      subprocess.Popen(
        ["bash", str(self._bridge_ensure_script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
      )
      logger.info("Triggered ensure_xpu_smi_bridge.sh to recover stale bridge")
    except OSError as exc:
      logger.debug("Could not launch ensure_xpu_smi_bridge.sh: %s", exc)

  def _read_xpu_smi_json_payload(self) -> dict | None:
    path = Path(self._xpu_smi_json_path)
    if not path.exists():
      return None
    try:
      return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
      return None

  @staticmethod
  def _bridge_payload_is_stale(payload: dict | None) -> bool:
    if payload is None:
      return True
    timestamp = payload.get("timestamp")
    if not isinstance(timestamp, (int, float)):
      return True
    return (time.time() - float(timestamp)) > XPU_SMI_JSON_MAX_AGE_S

  def _gpu_snapshot_from_json(self, payload: dict | None = None) -> dict | None:
    payload = payload if payload is not None else self._read_xpu_smi_json_payload()
    if payload is None:
      return None

    # The host bridge may publish CPU-only package telemetry via turbostat.
    # Do not treat that payload as authoritative GPU telemetry, or it masks
    # the normal GPU fallback probes and the dashboard regresses to a fake
    # GPU status like "cpu-only telemetry".
    has_gpu_signal = (
      isinstance(payload.get("percent"), (int, float))
      or isinstance(payload.get("power_watts"), (int, float))
    )
    if not has_gpu_signal and payload.get("status") == "cpu-only telemetry":
      return None

    if self._bridge_payload_is_stale(payload):
      self._ensure_bridge()
      return {
        "name": payload.get("name") or "Intel GPU",
        "percent": None,
        "power_watts": self._gpu_power_from_bridge(payload),
        "status": "xpu-smi bridge stale",
      }

    return {
      "name": payload.get("name") or "Intel GPU",
      "percent": payload.get("percent") if isinstance(payload.get("percent"), (int, float)) else None,
      "power_watts": self._gpu_power_from_bridge(payload),
      "status": payload.get("status") or "ok",
    }

  @staticmethod
  def _cpu_power_from_bridge(payload: dict | None) -> float | None:
    if SystemTelemetry._bridge_payload_is_stale(payload):
      return None
    value = payload.get("cpu_watts")
    if not isinstance(value, (int, float)):
      return None
    return round(float(value), 1)

  @staticmethod
  def _gpu_power_from_bridge(payload: dict | None) -> float | None:
    if SystemTelemetry._bridge_payload_is_stale(payload):
      return None
    value = payload.get("power_watts")
    if not isinstance(value, (int, float)):
      return None
    return round(float(value), 1)

  def _gpu_snapshot_from_xpu_smi(self) -> dict | None:
    if not self._xpu_smi_cmd:
      return None
    try:
      discovery = subprocess.run(
        [self._xpu_smi_cmd, "discovery", "-j"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5.0,
      )
      payload = json.loads(discovery.stdout or "{}")
      devices = payload.get("device_list") or []
      if not devices:
        return None
      device = devices[0]
      dump = subprocess.run(
        [self._xpu_smi_cmd, "dump", "-d", str(device.get("device_id", 0)), "-m", "0", "-i", "1", "-n", "1"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10.0,
      )
      percent = self._parse_xpu_dump_percent(dump.stdout or "")
      power_watts = None
      source = "xpu-smi dump"
      if percent is None:
        if shutil.which("sudo") and os.geteuid() != 0:
          sudo_stats = subprocess.run(
            ["sudo", "-n", self._xpu_smi_cmd, "stats", "-d", str(device.get("device_id", 0)), "-j"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10.0,
          )
          percent = self._parse_xpu_stats_percent(sudo_stats.stdout or "")
          power_watts = self._parse_xpu_stats_power(sudo_stats.stdout or "")
          if percent is not None:
            source = "xpu-smi stats (sudo)"
        if percent is None:
          stats = subprocess.run(
            [self._xpu_smi_cmd, "stats", "-d", str(device.get("device_id", 0)), "-j"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10.0,
          )
          percent = self._parse_xpu_stats_percent(stats.stdout or "")
          power_watts = self._parse_xpu_stats_power(stats.stdout or "")
          if percent is not None:
            source = "xpu-smi stats"
      elif shutil.which("sudo") and os.geteuid() != 0:
        sudo_stats = subprocess.run(
          ["sudo", "-n", self._xpu_smi_cmd, "stats", "-d", str(device.get("device_id", 0)), "-j"],
          check=False,
          capture_output=True,
          text=True,
          timeout=10.0,
        )
        power_watts = self._parse_xpu_stats_power(sudo_stats.stdout or "")
      if power_watts is None:
        stats = subprocess.run(
          [self._xpu_smi_cmd, "stats", "-d", str(device.get("device_id", 0)), "-j"],
          check=False,
          capture_output=True,
          text=True,
          timeout=10.0,
        )
        power_watts = self._parse_xpu_stats_power(stats.stdout or "")
      return {
        # Prefer an lspci-resolved name when available because xpu-smi discovery
        # can retain a raw PCI ID label even after pci.ids has been refreshed.
        "name": self._resolve_xpu_device_name(device),
        "percent": percent,
        "power_watts": power_watts,
        "status": "ok" if percent is not None else "xpu-smi reported no utilization",
        "source": source,
      }
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
      return None

  @staticmethod
  def _parse_xpu_dump_percent(output: str) -> float | None:
    if not output:
      return None
    try:
      rows = list(csv.DictReader(io.StringIO(output)))
    except Exception:
      return None
    if not rows:
      return None
    row = rows[-1]
    for key, value in row.items():
      if "GPU Utilization" not in key and "utilization of all GPU Engines" not in key:
        continue
      try:
        cleaned = value.strip()
        if not cleaned or cleaned.upper() == "N/A":
          return None
        return round(float(cleaned), 1)
      except (AttributeError, ValueError):
        return None
    return None

  @staticmethod
  def _parse_xpu_stats_percent(output: str) -> float | None:
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

  @staticmethod
  def _parse_xpu_stats_power(output: str) -> float | None:
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

  def _gpu_power_from_xpu_smi(self) -> float | None:
    if not self._xpu_smi_cmd:
      return None
    try:
      discovery = subprocess.run(
        [self._xpu_smi_cmd, "discovery", "-j"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5.0,
      )
      payload = json.loads(discovery.stdout or "{}")
      devices = payload.get("device_list") or []
      if not devices:
        return None
      device_id = str(devices[0].get("device_id", 0))
      stats = subprocess.run(
        [self._xpu_smi_cmd, "stats", "-d", device_id, "-j"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10.0,
      )
      return self._parse_xpu_stats_power(stats.stdout or "")
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
      return None

  def _resolve_xpu_device_name(self, device: dict) -> str:
    raw_name = device.get("device_name") or "Intel GPU"
    pci_bdf = device.get("pci_bdf_address")
    if not pci_bdf or not self._lspci_cmd:
      return raw_name

    try:
      proc = subprocess.run(
        [self._lspci_cmd, "-D", "-s", str(pci_bdf), "-nn"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5.0,
      )
    except (OSError, subprocess.TimeoutExpired):
      return raw_name
    if proc.returncode != 0 or not proc.stdout:
      return raw_name

    description = proc.stdout.strip().split(": ", 1)[-1]
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

  def _gpu_percent_from_xe_gtidle(self) -> float | None:
    """Compute GPU utilization from the xe driver's gtidle residency counters.

    The xe driver exposes cumulative idle_residency_ms per GT under
    /sys/class/drm/<card>/device/tile*/gt*/gtidle/idle_residency_ms.
    Utilization = 1 - Δidle / Δwall over the sampling interval.
    """
    if self._gpu_driver != "xe" or not self._gpu_card:
      return None

    paths = sorted(glob.glob(
      f"/sys/class/drm/{self._gpu_card}/device/tile*/gt*/gtidle/idle_residency_ms"
    ))
    if not paths:
      return None

    total_idle_ms = 0
    for p in paths:
      value = _read_text(p)
      if value is None:
        return None
      try:
        total_idle_ms += int(value)
      except ValueError:
        return None

    now = time.monotonic()
    prev = self._xe_gtidle_prev
    self._xe_gtidle_prev = (total_idle_ms, now)

    if prev is None:
      return None  # need two samples

    prev_idle_ms, prev_time = prev
    elapsed_ms = (now - prev_time) * 1000.0 * len(paths)  # scale to match summed idles
    delta_idle = total_idle_ms - prev_idle_ms

    if elapsed_ms <= 0:
      return None

    busy_frac = max(0.0, min(1.0, 1.0 - delta_idle / elapsed_ms))
    return round(busy_frac * 100.0, 1)

  def _gpu_percent_from_sysfs(self) -> float | None:
    candidate_paths = [
      f"/sys/class/drm/{self._gpu_card}/device/gpu_busy_percent",
      f"/sys/class/drm/{self._gpu_card}/device/gt_busy_percent",
      f"/sys/devices/pci0000:00/0000:00:02.0/gpu_busy_percent",
      f"/sys/devices/pci0000:00/0000:00:02.0/gt_busy_percent",
    ]
    for candidate in candidate_paths:
      value = _read_text(candidate)
      if value is None:
        continue
      try:
        return round(float(value), 1)
      except ValueError:
        continue
    return None

  def _gpu_power_from_sysfs(self) -> float | None:
    if not self._gpu_card:
      return None
    patterns = [
      f"/sys/class/drm/{self._gpu_card}/device/hwmon/hwmon*/power1_average",
      f"/sys/class/drm/{self._gpu_card}/device/hwmon/hwmon*/power1_input",
    ]
    for pattern in patterns:
      for candidate in sorted(glob.glob(pattern)):
        value = _read_text(candidate)
        if value is None:
          continue
        try:
          return round(float(value) / 1_000_000.0, 1)
        except ValueError:
          continue
    return None

  def _cpu_power_from_rapl(self) -> float | None:
    readings = []
    rapl_roots = sorted({
      *glob.glob("/sys/class/powercap/intel-rapl:*"),
      *glob.glob("/sys/class/powercap/intel-rapl/intel-rapl:*"),
    })
    for root in rapl_roots:
      root_path = Path(root)
      name = _read_text(str(root_path / "name")) or ""
      if not name.startswith("package-"):
        continue

      power_uw = _read_text(str(root_path / "power_uw"))
      if power_uw is not None:
        try:
          readings.append(float(power_uw) / 1_000_000.0)
          continue
        except ValueError:
          pass

      energy_uj = _read_text(str(root_path / "energy_uj"))
      max_energy_uj = _read_text(str(root_path / "max_energy_range_uj"))
      if energy_uj is None:
        continue
      try:
        energy_value = int(energy_uj)
      except ValueError:
        continue

      now = time.monotonic()
      prev = self._rapl_prev.get(root)
      self._rapl_prev[root] = (energy_value, now)
      if prev is None:
        continue

      prev_energy, prev_time = prev
      elapsed = now - prev_time
      if elapsed < _RAPL_SAMPLE_MIN_INTERVAL_S:
        continue

      delta = energy_value - prev_energy
      if delta < 0 and max_energy_uj is not None:
        try:
          delta += int(max_energy_uj)
        except ValueError:
          continue
      if delta < 0:
        continue

      readings.append(delta / elapsed / 1_000_000.0)

    if not readings:
      return None
    return round(sum(readings), 1)

  def _gpu_percent_from_intel_gpu_top(self) -> float | None:
    if not self._gpu_tool or not os.path.exists("/dev/dri"):
      return None

    cmd = [self._gpu_tool, "-J", "-s", "200", "-l", "1"]
    try:
      proc = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=3.0,
      )
      output = (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as exc:
      logger.debug("intel_gpu_top probe failed: %s", exc)
      return None

    percent = self._parse_intel_gpu_top_output(output)
    if percent is None:
      logger.debug("intel_gpu_top output did not contain a render busy metric")
    return percent

  @staticmethod
  def _parse_intel_gpu_top_output(output: str) -> float | None:
    if not output:
      return None

    for line in reversed(output.splitlines()):
      line = line.strip().rstrip(",")
      if not line.startswith("{"):
        continue
      try:
        payload = json.loads(line)
      except json.JSONDecodeError:
        continue
      engines = payload.get("engines") or {}
      candidates = []
      for name, info in engines.items():
        if not isinstance(info, dict):
          continue
        if any(token in name.lower() for token in ("render", "3d", "compute")):
          busy = info.get("busy")
          if isinstance(busy, (int, float)):
            candidates.append(float(busy))
      if candidates:
        return round(max(candidates), 1)
    return None