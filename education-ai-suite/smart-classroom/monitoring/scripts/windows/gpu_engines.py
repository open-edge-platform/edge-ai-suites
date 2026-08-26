# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Shared access to the Windows ``GPU Engine`` performance counters.

Windows exposes every accelerator command streamer — GPU *and* NPU — as an
instance of the single ``GPU Engine`` performance object, which is what Task
Manager's GPU/NPU graphs read. Instance names look like::

    pid_4132_luid_0x00000000_0x0000E371_phys_0_eng_13_engtype_Neural

``collect_gpu.py`` and ``collect_npu.py`` both need to enumerate those
instances, tell the adapters apart and sample the same rate-based counter, so
that plumbing lives here once — and, more importantly, both collectors then
classify adapters identically and can never double count the same engine.

Adapter classification (by LUID, i.e. per physical adapter):

* **render adapter** — exposes an ``engtype_3D`` engine. This is a GPU.
* **NPU adapter** — exposes ``engtype_Neural`` but no 3D engine. On Intel
  platforms this is "Intel(R) AI Boost".

The distinction matters because a modern Intel iGPU *also* exposes a Neural
engine (its XMX/AI block), and that engine — not ``engtype_Compute`` — is where
OpenVINO's ``device: GPU`` inference actually runs on Windows. Measured on
Arrow Lake with OpenVINO 2026.3 while looping a matmul model:

    device=GPU  -> luid_...E371 (iGPU) engtype_Neural eng_13 ~94%
    device=NPU  -> luid_...E7CC (AI Boost) engtype_Neural eng_0 ~43%

so the GPU's Neural engine belongs to the GPU's compute figure, and only the
NPU adapter's Neural engine belongs to the NPU figure.
"""

import logging
import re
import time

import win32pdh

logger = logging.getLogger(__name__)

ENGINE_OBJECT = "GPU Engine"
UTILIZATION_COUNTER = "Utilization Percentage"

ENGTYPE_3D = "3d"
ENGTYPE_NEURAL = "neural"
ENGTYPE_COMPUTE = "compute"

# pid_4_luid_0x00000000_0x0000E7CC_phys_0_eng_0_engtype_Neural
_LUID_RE = re.compile(r"luid_0x[0-9A-Fa-f]+_0x[0-9A-Fa-f]+", re.IGNORECASE)
# Some command streamers report an empty engine type (``..._eng_9_engtype_``);
# they are unclassifiable and are left out of every bucket.
_ENGTYPE_RE = re.compile(r"engtype_(\w+)", re.IGNORECASE)


def enumerate_engines():
    """Return ``[(instance, luid, engtype)]`` for every ``GPU Engine`` instance.

    ``luid`` is lower-cased (the adapter key) and ``engtype`` is lower-cased
    (e.g. ``"3d"``, ``"neural"``, ``"videodecode"``). Instances are per-process
    and come and go with the workload, so callers re-enumerate every sample.
    """
    try:
        _, instances = win32pdh.EnumObjectItems(
            None, None, ENGINE_OBJECT, win32pdh.PERF_DETAIL_WIZARD
        )
    except Exception as e:
        logger.debug(f"Cannot enumerate '{ENGINE_OBJECT}' instances: {e}")
        return []

    engines = []
    for inst in instances:
        luid_match = _LUID_RE.search(inst)
        engtype_match = _ENGTYPE_RE.search(inst)
        if not luid_match or not engtype_match:
            continue
        engines.append(
            (inst, luid_match.group(0).lower(), engtype_match.group(1).lower())
        )
    return engines


def classify_adapters(engines):
    """Split the adapters seen in ``engines`` into ``(render, npu)`` LUID sets.

    An adapter with a 3D engine is a GPU; an adapter with a Neural engine but
    no 3D engine is a dedicated NPU. Adapters with neither belong to neither
    collector and are dropped.
    """
    engtypes_by_adapter = {}
    for _inst, luid, engtype in engines:
        engtypes_by_adapter.setdefault(luid, set()).add(engtype)

    render = {
        luid for luid, types in engtypes_by_adapter.items() if ENGTYPE_3D in types
    }
    npu = {
        luid
        for luid, types in engtypes_by_adapter.items()
        if ENGTYPE_NEURAL in types and ENGTYPE_3D not in types
    }
    return render, npu


def sample_utilization(instances, settle_seconds=0.2):
    """Sum ``Utilization Percentage`` per instance, grouped by the caller's key.

    Args:
        instances: iterable of ``(instance_name, bucket)`` pairs. Every
            instance's utilization is added to its bucket, which is how Task
            Manager reports an engine: the sum over the processes using it.
        settle_seconds: gap between the two collections. ``Utilization
            Percentage`` is rate based, so a single collection always reads 0.

    Returns:
        ``{bucket: percentage}`` for the buckets that resolved, each clamped to
        100 so a value can always be read as a percentage of one engine.
    """
    instances = list(instances)
    if not instances:
        return {}

    query = win32pdh.OpenQuery()
    counters = []
    try:
        for inst, bucket in instances:
            try:
                counters.append(
                    (
                        win32pdh.AddCounter(
                            query, f"\\{ENGINE_OBJECT}({inst})\\{UTILIZATION_COUNTER}"
                        ),
                        bucket,
                    )
                )
            except Exception as e:
                logger.debug(f"Skipping {inst}: {e}")

        win32pdh.CollectQueryData(query)
        time.sleep(settle_seconds)
        win32pdh.CollectQueryData(query)

        totals = {}
        for counter, bucket in counters:
            try:
                _, val = win32pdh.GetFormattedCounterValue(
                    counter, win32pdh.PDH_FMT_DOUBLE
                )
            except Exception:
                continue
            totals[bucket] = totals.get(bucket, 0.0) + val
    finally:
        win32pdh.CloseQuery(query)

    return {bucket: round(min(val, 100.0), 2) for bucket, val in totals.items()}
