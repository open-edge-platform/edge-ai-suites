#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Shared Intel GPU engine-class definitions used by gpu_pid_analyzer and
visualize_gpu.
"""

import re
from typing import Dict, List

# ──────────────────────────────────────────────────────────────────────────────
# Engine-class mapping  (canonical label → regex)
# ──────────────────────────────────────────────────────────────────────────────

ENGINE_CLASSES: Dict[str, re.Pattern] = {
    'Render/3D': re.compile(r'render|3d',                      re.I),
    'Blitter':   re.compile(r'blitter|blt',                    re.I),
    'Video':     re.compile(r'^video$',                        re.I),
    'VE':        re.compile(r'videoenhance|video_enhance|ve\b', re.I),
}

ENG_COLS: List[str] = list(ENGINE_CLASSES.keys())

ENG_COLORS: Dict[str, str] = {
    'Render/3D': '#e07b39',
    'Blitter':   '#4c9de0',
    'Video':     '#6abf6a',
    'VE':        '#b565c9',
}
