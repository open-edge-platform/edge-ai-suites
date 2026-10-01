#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Per-stream reporting: summary figures and the per-object loiter table."""

import time

from config import LOITER_THRESHOLD_S, TABLE_STALE_S


def _track_dwell(trk):
    """gvaanalytics' dwell time for this track, else the local first/last span."""
    native = trk.get("native_dwell_s")
    if native is not None:
        return max(0.0, native)
    return max(0.0, trk["last"] - trk["first"])


def _stream_snapshot(peer_id, sess, now):
    # Rows first: every summary figure is derived from this same list, so the
    # headline numbers can never disagree with the table. Rows not refreshed
    # within TABLE_STALE_S are withheld rather than shown indefinitely.
    rows = []
    for tid, trk in sess["tracks"].items():
        if now - trk.get("wall_last", 0.0) > TABLE_STALE_S:
            continue
        dwell = _track_dwell(trk)
        rows.append({
            "id": str(tid),
            "label": trk.get("label", "object"),
            "zone": ", ".join(trk.get("zones") or []) or "-",
            "status": "Loitering" if dwell >= LOITER_THRESHOLD_S else "Present",
            "dwell_s": round(dwell, 2),
            "entry_time": time.strftime("%H:%M:%S", time.localtime(trk.get("entry_wall", now))),
        })
    rows.sort(key=lambda r: r["dwell_s"], reverse=True)

    dwells = [r["dwell_s"] for r in rows]
    max_dwell = max(dwells) if dwells else 0.0
    loiter_count = sum(1 for d in dwells if d >= LOITER_THRESHOLD_S)

    times = list(sess["msg_times"])
    if len(times) >= 2:
        elapsed = times[-1] - times[0]
        fps = round((len(times) - 1) / elapsed, 2) if elapsed > 0 else 0.0
    else:
        fps = 0.0

    if now - sess.get("last_activity", 0.0) > 5.0:
        detection_state = "no-data"
    else:
        detection_state = sess.get("detection_state", "no-data")

    return {
        "peer_id": peer_id,
        "topic": sess["topic"],
        "model": sess["model"],
        "device": sess["device"],
        "fps": fps,
        "max_dwell_s": round(max_dwell, 2),
        "loiter_count": loiter_count,
        "object_count": len(rows),
        "zone": sess["zone"],
        "frame_time_source": sess.get("frame_time_source", "wallclock"),
        "state": sess.get("state", "RUNNING"),
        "detection_state": detection_state,
        "objects": rows,
    }


