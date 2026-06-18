#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
Filter vippet's supported_models.yaml before model installation.

Removes:
  - huggingface models (large, require auth, not needed here)
  - models with broken download scripts (see BROKEN set below)

Usage:
  python3 filter_models.py <path-to-supported_models.yaml>
"""

import sys
import yaml

# Pallet defect detection model is broken in this downloader,
# needs a newer version of DLSPS - which means a newer version of ViPPET, with newer model-downloader service
# TODO: remove this exclusion once ViPPET is released and updated in this stack.
BROKEN = {"pallet_defect_detection"}


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
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <supported_models.yaml>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
