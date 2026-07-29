#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
Filter vippet's supported_models.yaml and pipelines before deployment.

Removes from supported_models.yaml:
  - huggingface models (large, require auth, not needed here)
  - models with broken download scripts (see BROKEN set below)

Removes from the pipelines directory (see REMOVE_PIPELINES below):
  - pipelines that depend on removed models (defect-detection, video-summarization-vlm)

Usage:
  python3 filter_models.py <path-to-supported_models.yaml> [<pipelines-dir>]
"""

import os
import sys
import yaml

# Pallet defect detection model is broken in this downloader,
# needs a newer version of DLSPS - which means a newer version of ViPPET, with newer model-downloader service
# TODO: remove this exclusion once ViPPET is released and updated in this stack.
BROKEN = {"pallet_defect_detection"}

# Pipelines that depend on models removed above (huggingface / broken).
# defect-detection depends on pallet_defect_detection; video-summarization-vlm
# depends on the gemma3 huggingface model.
REMOVE_PIPELINES = {"defect-detection.yaml", "video-summarization-vlm.yaml"}


def filter_pipelines(pipelines_dir: str) -> None:
    removed = []
    for name in REMOVE_PIPELINES:
        path = os.path.join(pipelines_dir, name)
        if os.path.exists(path):
            os.remove(path)
            removed.append(name)
    print(
        f"✓ pipelines filtered "
        f"({len(removed)} removed: {', '.join(sorted(removed)) or 'none already absent'})"
    )


def main(src: str) -> None:
    models = yaml.safe_load(open(src))
    filtered = [
        m for m in models
        if m.get("source") != "huggingface"
        and m.get("name") not in BROKEN
    ]
    yaml.dump(filtered, open(src, "w"), default_flow_style=False, allow_unicode=True)
    print(
        f"✓ supported_models.yaml filtered "
        f"({len(filtered)}/{len(models)} models kept, "
        f"huggingface and broken models excluded)"
    )


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print(f"Usage: {sys.argv[0]} <supported_models.yaml> [<pipelines-dir>]", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
    if len(sys.argv) == 3:
        filter_pipelines(sys.argv[2])
