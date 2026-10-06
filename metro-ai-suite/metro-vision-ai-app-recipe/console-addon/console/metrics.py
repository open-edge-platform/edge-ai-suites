#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Utilisation, resolved from candidate Prometheus expressions."""

import requests

from config import PROMETHEUS_URL

def _prometheus_query(expr):
    try:
        r = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": expr}, timeout=5)
        r.raise_for_status()
        result = r.json().get("data", {}).get("result", [])
        if not result:
            return None
        return float(result[0]["value"][1])
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return None


def _prom_first(candidates):
    """Evaluate an ordered list of candidate expressions; use the first hit.

    Series names differ between exporters that may be deployed. Binding a
    field to a single expression renders that gauge as n/a on a host whose
    exporter uses different names.
    """
    for expr in candidates:
        v = _prometheus_query(expr)
        if v is not None:
            return v
    return None


def _clamp_power(v):
    # A power reading below zero or above 2000 W is a counter artefact.
    if v is None or v < 0 or v > 2000:
        return None
    return v


def _gpu_engine_ratios():
    try:
        r = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": "qmmd_gpu_engine_utilization_ratio"},
            timeout=5,
        )
        r.raise_for_status()
        result = r.json().get("data", {}).get("result", [])
    except (requests.RequestException, ValueError, KeyError):
        return {}
    engines = {}
    for item in result:
        try:
            eng = item.get("metric", {}).get("engine", "unknown")
            val = float(item["value"][1])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        engines[eng] = max(engines.get(eng, 0.0), val)
    return engines


def _gpu_percent(engines):
    # GPU utilisation MUST be taken from the compute-engine series:
    # averaging across all engines dilutes the signal because most engines
    # are idle during inference, and the legacy aggregate series reports
    # zero on supported builds. The compute engine's label varies by
    # qmassa version/GPU generation - "ccs" on some, "compute" on others.
    for name in ("ccs", "compute"):
        if name in engines:
            return round(engines[name] * 100, 1)
    return _prom_first(["max(qmmd_gpu_utilization_ratio)*100"])


def collect_metrics():
    engines = _gpu_engine_ratios()
    cpu_percent = _prom_first([
        "avg(qmmd_cpu_utilization_ratio)*100",
        "avg(cpu_usage_percentage)",
        "100-avg(cpu_usage_idle)",
    ])
    cpu_freq = _prom_first([
        "avg(qmmd_cpu_frequency_hertz)/1000000",
        "avg(cpu_frequency_avg_frequency)/1000",
    ])
    gpu_percent = _gpu_percent(engines)
    gpu_mem_used = _prom_first(["max(qmmd_gpu_memory_used_bytes)", "max(gpu_memory_used_bytes)"])
    gpu_mem_total = _prom_first(["max(qmmd_gpu_memory_total_bytes)", "max(gpu_memory_total_bytes)"])
    gpu_freq = _prom_first(["max(qmmd_gpu_actual_frequency_hertz)/1000000", "max(gpu_frequency)"])
    gpu_power = _clamp_power(_prom_first(["max(qmmd_gpu_power_watts)", "max(gpu_power)"]))
    npu_percent = _prom_first(["max(qmmd_npu_utilization_ratio)*100", "avg(npu_utilization)"])
    npu_mem_used = _prom_first(["max(qmmd_npu_memory_used_bytes)", "max(npu_memory_mb)*1000000"])
    npu_power = _clamp_power(_prom_first(["max(qmmd_npu_power_watts)", "max(npu_power)"]))
    mem_percent = _prom_first(["avg(qmmd_memory_utilization_ratio)*100", "avg(mem_used_percent)"])
    mem_used = _prom_first(["max(qmmd_memory_used_bytes)", "max(mem_used)"])
    mem_total = _prom_first(["max(qmmd_memory_total_bytes)", "max(mem_total)"])
    return {
        "cpu": {"percent": cpu_percent, "freq_mhz": cpu_freq},
        "gpu": {
            "percent": gpu_percent,
            "engines": engines,
            "mem_used_bytes": gpu_mem_used,
            "mem_total_bytes": gpu_mem_total,
            "freq_mhz": gpu_freq,
            "power_w": gpu_power,
        },
        "npu": {"percent": npu_percent, "mem_used_bytes": npu_mem_used, "power_w": npu_power},
        "mem": {"percent": mem_percent, "used_bytes": mem_used, "total_bytes": mem_total},
    }


# --------------------------------------------------------------------------
# 6. MQTT ingestion (BACKEND-SPEC.md §5)
# --------------------------------------------------------------------------

