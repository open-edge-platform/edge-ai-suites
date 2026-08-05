#!/usr/bin/env python3
"""List Basler cameras visible on this host and print their serial numbers.

Usage:
    python3 scripts/list_basler.py

Prints one line per camera in the form:
    serial=<serial>  model=<model>

Exit codes:
    0 — pypylon available and enumeration completed (even if zero cameras)
    2 — pypylon not installed (prints an install hint on stderr)
    3 — pypylon raised while enumerating (prints the error on stderr)
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from pypylon import pylon  # type: ignore[import-not-found]
    except ImportError:
        sys.stderr.write(
            "[list_basler] pypylon is not installed on this host.\n"
            "  Install with:  python3 -m pip install pypylon\n"
            "  (or run 'make up' once and use the containerized enumeration.)\n"
        )
        return 2

    try:
        devices = pylon.TlFactory.GetInstance().EnumerateDevices()
    except Exception as exc:  # pypylon raises RuntimeError family
        sys.stderr.write(f"[list_basler] pypylon enumeration failed: {exc}\n")
        return 3

    if not devices:
        print("  (no Basler cameras detected)")
        return 0

    for dev in devices:
        print(f"  serial={dev.GetSerialNumber()}  model={dev.GetModelName()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
