#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Frame-time units, zone occupancy, dwell and the stream snapshot."""

import time

from config import (TABLE_STALE_S, TRACK_TTL_S, ZONE_ID)

def _native_dwell(obj):
    """gvaanalytics' own dwell time for this session's zone, or None.

    Preferred over recomputing from bounding boxes: it is what the pipeline
    itself treats as authoritative and it honours object-retention.
    """
    for dt in obj.get("dwell_times") or []:
        if isinstance(dt, dict) and dt.get("zone_id") == ZONE_ID:
            return dt.get("dwell_time_sec")
    return None


def _extract_candidates(payload, metadata):
    """Frame-time candidates in priority order.

    Units come from the key, never the value's magnitude: a short clip's
    presentation timestamp occupies the same numeric range as microseconds.
    """
    cands = []
    if isinstance(metadata, dict) and "timestamp" in metadata:
        cands.append(("metadata.timestamp", metadata["timestamp"]))
    if isinstance(metadata, dict) and "time" in metadata:
        cands.append(("metadata.time", metadata["time"]))
    if "timestamp" in payload:
        cands.append(("timestamp", payload["timestamp"]))
    return cands


def _normalise_frame_time(value, key):
    v = float(value)
    if key in ("metadata.timestamp", "metadata.time"):
        # GStreamer PTS / epoch, both carried in nanoseconds.
        return v / 1e9
    if key == "timestamp":
        # Top-level timestamp is already epoch seconds.
        return v
    return v


def _resolve_frame_time(sess, payload, metadata, now):
    """Frame time for this message, locked to the key seen on the first one.

    Both metadata.timestamp (PTS from stream start) and metadata.time (epoch)
    occur in the feed, so the time base must not change mid-stream.
    """
    cands = _extract_candidates(payload, metadata)
    locked_key = sess.get("time_key")
    if locked_key is not None:
        for k, v in cands:
            if k == locked_key:
                sess["frame_time_source"] = "frame"
                return _normalise_frame_time(v, k)
        # Hold the previous reading rather than switch to an incompatible key.
        sess["frame_time_source"] = "frame" if sess.get("last_frame_ts") is not None else "wallclock"
        return sess.get("last_frame_ts", now)
    if cands:
        k, v = cands[0]
        sess["time_key"] = k
        sess["frame_time_source"] = "frame"
        return _normalise_frame_time(v, k)
    sess["frame_time_source"] = "wallclock"
    return now


def _object_label(obj):
    """Best-effort class label, tolerating the several shapes DL Streamer emits."""
    for key in ("label", "roi_type", "type", "class", "class_name"):
        v = obj.get(key)
        if isinstance(v, str) and v:
            return v
    det = obj.get("detection")
    if isinstance(det, dict):
        for key in ("label", "class_name", "class"):
            v = det.get(key)
            if isinstance(v, str) and v:
                return v
        lid = det.get("label_id")
        if lid is not None:
            return "class %s" % lid
    # Some pipelines publish only geometry. Reporting the region keeps the
    # column meaningful instead of blank; attach a model-proc with a label
    # list to the pipeline for true class names.
    rid = obj.get("region_id")
    return ("region %s" % rid) if rid is not None else "object"


def _is_detection(obj):
    """False for the region gvaattachroi adds to every frame.

    That region also carries dwell metadata, so it must be excluded by shape.
    Detections are its children and carry a parent_id; it has none. Keying on
    the class label instead would drop detections from an unlabelled model.
    """
    return obj.get("parent_id") is not None


def _update_zone_analytics(sess, objects, metadata, frame_ts, now):
    for obj in objects:
        if not isinstance(obj, dict) or not _is_detection(obj):
            continue
        # gvaanalytics decides zone membership, and it is the same component
        # the overlay and Grafana report from.
        native_dwell = _native_dwell(obj)
        if native_dwell is None:
            continue
        tid = obj.get("id") or obj.get("object_id") or obj.get("track_id") or f"anon-{id(obj)}"
        trk = sess["tracks"].get(tid)
        label = _object_label(obj)
        if trk is None:
            sess["tracks"][tid] = {"first": frame_ts, "last": frame_ts, "wall_last": now,
                                   "label": label, "entry_wall": now, "native_dwell_s": native_dwell}
        else:
            trk["last"] = frame_ts
            trk["wall_last"] = now
            trk["native_dwell_s"] = native_dwell
            if label != "object":
                trk["label"] = label

    # Evicted on a time-to-live, not on the reporting interval, so a briefly
    # occluded subject is not discarded early.
    ttl_cutoff = now - TRACK_TTL_S
    for tid in list(sess["tracks"].keys()):
        if sess["tracks"][tid]["wall_last"] < ttl_cutoff:
            del sess["tracks"][tid]

    sess["msg_times"].append(now)
    sess["last_frame_ts"] = frame_ts
    sess["last_activity"] = now
    if objects:
        sess["last_detection_wall"] = now
    # One empty frame is normal; only a sustained absence means the model is
    # producing nothing. Judging per frame made the status flap.
    since = now - sess.get("last_detection_wall", 0.0)
    sess["detection_state"] = "ok" if since <= TABLE_STALE_S else "no-detections"
