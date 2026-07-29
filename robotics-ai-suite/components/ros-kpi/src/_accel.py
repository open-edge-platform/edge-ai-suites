# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""Intel acceleration shim.

Provides a numpy-compatible ``np`` namespace backed by Intel dpnp (Data
Parallel NumPy, dispatches to Intel iGPU/CPU via oneAPI SYCL / level-zero)
when available, with transparent fallback to standard numpy.  Also configures
Intel MKL thread count and exposes numexpr as ``ne`` for fast vectorised
expression evaluation via Intel VML.

Usage in source files::

    from _accel import np           # drop-in numpy replacement
    from _accel import np, ne       # also get numexpr (None if not installed)

The active backend is reported in ``_BACKEND`` ("dpnp" | "numpy").

dpnp arrays implement the ``__array__`` protocol, so they are accepted
transparently by matplotlib, psutil, json serialisation and other stdlib/
third-party code that calls ``numpy.asarray()`` internally.
"""

import os

# ── numpy / dpnp ─────────────────────────────────────────────────────────────
try:
    import dpnp as np       # Intel oneAPI SYCL — dispatches to iGPU via level-zero
    _BACKEND: str = "dpnp"
except ImportError:
    import numpy as np      # type: ignore[no-redef]
    _BACKEND = "numpy"

# ── numexpr (Intel VML-backed expression evaluator) ──────────────────────────
try:
    import numexpr as ne    # type: ignore[import-not-found]
    _NE: bool = True
except ImportError:
    ne = None               # type: ignore[assignment]
    _NE = False

# ── Intel MKL threading ───────────────────────────────────────────────────────
try:
    import mkl as _mkl
    _mkl.set_num_threads(len(os.sched_getaffinity(0)))
except (ImportError, OSError, AttributeError):
    pass

__all__ = ["np", "ne", "_BACKEND", "_NE"]
