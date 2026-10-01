#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Model discovery, IR preflight, source and pipeline selection."""

import hashlib
import os
import re
import xml.etree.ElementTree as ET

import requests

from config import (MODEL_CACHE, MODEL_CACHE_TTL_S, MODEL_ROOT,
                    PIPELINE_SERVER_URL, SOURCES)

import time

def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "model"


def _ir_input_shape(xml_path):
    """Read the first Parameter layer's output shape from an IR XML file.

    Returns a list of ints, -1 for a dynamic dimension, or None when the
    file cannot be parsed. Classification is generic IR introspection; no
    model family is named or special-cased.
    """
    try:
        root = ET.parse(xml_path).getroot()
        for layer in root.iter("layer"):
            if layer.get("type") != "Parameter":
                continue
            port = layer.find("./output/port")
            if port is None:
                continue
            dims = []
            for dim in port.findall("dim"):
                text = (dim.text or "").strip()
                try:
                    val = int(text)
                except ValueError:
                    val = -1
                dims.append(val if val > 0 else -1)
            return dims
        return None
    except (ET.ParseError, OSError):
        return None


def _model_compatibility(shape):
    if shape is None:
        return "unknown", None
    if len(shape) >= 4 and (shape[2] == -1 or shape[3] == -1):
        detail = (
            "This model has a dynamic spatial input shape. The GPU and NPU "
            "plugins reject it, and the CPU decodes frames without producing "
            "detections. Reshape it to a fixed size (see prepare-model.sh) "
            "before use."
        )
        return "dynamic-spatial", detail
    return "ok", None


def discover_models(force=False):
    now = time.time()
    if not force and MODEL_CACHE["data"] is not None and (now - MODEL_CACHE["ts"]) < MODEL_CACHE_TTL_S:
        return MODEL_CACHE["data"]

    models = []
    seen_ids = set()
    if os.path.isdir(MODEL_ROOT):
        for root, _dirs, files in os.walk(MODEL_ROOT):
            for fn in files:
                if not fn.endswith(".xml"):
                    continue
                stem = fn[:-4]
                bin_path = os.path.join(root, stem + ".bin")
                if not os.path.isfile(bin_path):
                    continue
                xml_path = os.path.join(root, fn)
                rel_dir = os.path.relpath(root, MODEL_ROOT)
                dir_name = os.path.basename(root)
                precision = dir_name if dir_name.upper() in ("FP16", "FP32", "INT8", "FP16-INT8") else None

                # Model identifier uniqueness (PIPELINE.md §14): qualify with
                # the containing directory when it differs from the model
                # file name, so two IRs sharing a file name in sibling
                # directories cannot silently displace each other.
                if dir_name.lower() == stem.lower():
                    ident = _slug(rel_dir)
                else:
                    ident = _slug(os.path.join(rel_dir, stem))
                while ident in seen_ids:
                    ident = f"{ident}-{len(models)}"
                seen_ids.add(ident)

                label = f"{stem} ({precision})" if precision else stem

                model_proc = None
                same_dir_proc = os.path.join(root, stem + ".json")
                parent_proc = os.path.join(os.path.dirname(root), stem + ".json")
                if os.path.isfile(same_dir_proc):
                    model_proc = same_dir_proc
                elif os.path.isfile(parent_proc):
                    model_proc = parent_proc

                shape = _ir_input_shape(xml_path)
                compatibility, detail = _model_compatibility(shape)

                models.append({
                    "id": ident,
                    "label": label,
                    "model": xml_path,
                    "model_proc": model_proc,
                    "compatibility": compatibility,
                    "input_shape": shape,
                    "compatibility_detail": detail,
                })

    models.sort(key=lambda m: m["label"].lower())
    result = {"models": models, "discovered": True}
    if not models:
        result["message"] = "no model is installed in the model store"
    MODEL_CACHE["data"] = result
    MODEL_CACHE["ts"] = now
    return result


# --------------------------------------------------------------------------
# 3. Pipeline selection and model-instance identity (PIPELINE.md §2)
# --------------------------------------------------------------------------

def _select_pipeline(device):
    """Select a pipeline whose *version* carries the device.

    The released pipelines are published under one name with the device in
    the version field. Selecting by name alone never selects a device and
    silently falls through to whichever entry is first.
    """
    r = requests.get(f"{PIPELINE_SERVER_URL}/pipelines", timeout=5)
    r.raise_for_status()
    entries = r.json()
    if not isinstance(entries, list):
        return None
    dev = device.lower()
    for e in entries:
        version = str(e.get("version", ""))
        if version.lower().endswith(f"_{dev}"):
            return e
    for e in entries:
        version = str(e.get("version", ""))
        if dev in version.lower():
            return e
    return None


def _model_instance_id(model_path, device, unique):
    """Derive a model-instance-id from the model path, device and `unique`.

    DL Streamer caches a loaded network against this identifier, so reusing
    it for a different model binds the request to the stale network -
    `unique` (the new session's own peer_id) rules that out entirely. It is
    deliberately NOT shared across concurrent launches of the very same
    model+device either: two separate pipeline instances told to share one
    cached network can starve each other's inference requests once one of
    them is stopped uncleanly, silently wedging every later launch that
    reuses that id (observed live - fixed only by restarting the whole
    pipeline server, which clears the cache). A fresh id per launch costs a
    model recompile per stream instead of reusing a cached one, which is
    the right trade for every stream actually working.
    """
    digest = hashlib.sha256(f"{model_path}|{device}|{unique}".encode("utf-8")).hexdigest()[:12]
    return f"console-{digest}"


def _extract_instance_id(resp):
    try:
        data = resp.json()
    except ValueError:
        return resp.text.strip()
    if isinstance(data, dict):
        return data.get("id") or data.get("instance_id") or resp.text.strip()
    if isinstance(data, str):
        return data
    return resp.text.strip()


_ALLOWED_RTSP_SCHEMES = ("rtsp://", "rtsps://")


def _resolve_source_uri(source_id, rtsp_override=None):
    if rtsp_override:
        # Free-text input is only ever meant to be a camera RTSP URL; accepting
        # any scheme here would let a caller point the pipeline server at an
        # arbitrary internal endpoint (SSRF) under the guise of a video source.
        if not str(rtsp_override).startswith(_ALLOWED_RTSP_SCHEMES):
            return None
        return rtsp_override
    for s in SOURCES:
        if s.get("id") == source_id:
            return s.get("uri")
    # Only pre-registered SOURCES entries or an explicit rtsp:// override may
    # name a stream - an arbitrary source_id is never treated as a raw URI.
    return None


# --------------------------------------------------------------------------
# 4. Frame time (BACKEND-SPEC.md §5.1 / §11) and zone/dwell analytics (§6)
# --------------------------------------------------------------------------

