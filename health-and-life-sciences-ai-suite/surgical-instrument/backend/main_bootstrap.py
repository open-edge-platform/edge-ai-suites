"""Standalone bootstrap CLI.

Usage:
    python -m backend.main_bootstrap [--config path/to/model.yaml]

Runs the cache-first orchestrator once and prints each state transition.
Exits 0 if the pipeline reaches ``ready``, 1 on any error.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from backend.bootstrap.orchestrator import Orchestrator


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config" / "model.yaml"),
        help="Path to model.yaml",
    )
    ap.add_argument("--json", action="store_true", help="Emit newline-delimited JSON events")
    args = ap.parse_args()

    def on_event(event: dict):
        if args.json:
            print(json.dumps(event), flush=True)
            return
        state = event.get("state", "?")
        phase = event.get("phase", "?")
        msg = event.get("message", "")
        print(f"[{time.strftime('%H:%M:%S')}] {state:>22} | {phase:<8} | {msg}", flush=True)

    orch = Orchestrator(args.config, progress=on_event)
    try:
        result = orch.run()
    except Exception as exc:  # noqa: BLE001
        print(f"[main_bootstrap] FAILED: {exc}", file=sys.stderr)
        return 1

    print("\n=== final state ===")
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("state") == "ready" else 1


if __name__ == "__main__":
    sys.exit(main())
