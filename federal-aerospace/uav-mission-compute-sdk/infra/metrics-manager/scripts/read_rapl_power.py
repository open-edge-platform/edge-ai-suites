#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""RAPL package power reader — Telegraf execd plugin.

Reads the Intel RAPL energy counter from sysfs and computes instantaneous
package power (Watts) as the derivative of the monotonic energy counter.
Emits InfluxDB line protocol to stdout once per second.

On hosts without a RAPL interface the process parks itself silently so
Telegraf's execd restart loop does not spam the log.
"""

import os
import sys
import time

RAPL_ENERGY = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"
HOSTNAME = os.environ.get("METRICS_MANAGER_HOSTNAME") or os.uname()[1]
INTERVAL_S = 1.0
IDLE_SLEEP_S = 3600


def idle_forever(reason: str) -> None:
    print(f"# rapl_power unavailable: {reason}", file=sys.stderr, flush=True)
    while True:
        time.sleep(IDLE_SLEEP_S)


if not os.path.exists(RAPL_ENERGY):
    idle_forever(f"{RAPL_ENERGY} not found")

prev_uj: int | None = None
prev_t: float | None = None

while True:
    try:
        with open(RAPL_ENERGY) as f:
            uj = int(f.read().strip())
        now = time.time()
        if prev_uj is not None and prev_t is not None:
            dt = now - prev_t
            if dt > 0:
                power_w = (uj - prev_uj) / 1_000_000.0 / dt
                ts_ns = int(now * 1e9)
                print(
                    f"rapl_power,host={HOSTNAME} power_w={power_w:.3f} {ts_ns}",
                    flush=True,
                )
        prev_uj = uj
        prev_t = now
    except Exception as exc:
        print(f"# rapl_power read error: {exc}", file=sys.stderr, flush=True)
    time.sleep(INTERVAL_S)
