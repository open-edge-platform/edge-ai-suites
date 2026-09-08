#!/usr/bin/env python3
"""List connected Basler cameras (serial + model) for use as SERIAL=<...>."""
from __future__ import annotations

import sys


def main() -> int:
    try:
        from pypylon import pylon
    except ImportError:
        print("pypylon not installed — run 'pip install pypylon'", file=sys.stderr)
        return 1

    devices = pylon.TlFactory.GetInstance().EnumerateDevices()
    if not devices:
        print("no Basler devices found")
        return 1

    for d in devices:
        print(f"{d.GetSerialNumber()}\t{d.GetModelName()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
