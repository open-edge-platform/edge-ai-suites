#!/usr/bin/env python3
"""
wandering_metrics.py — helper for wandering_run.sh

Subcommands
-----------
  sample-rtf <rtf_log>
      Read /clock text from stdin, compute RTF (sim-time / wall-time),
      append one float per 0.5 wall-seconds to <rtf_log>.
      Usage:
          ros2 topic echo /clock | python3 wandering_metrics.py sample-rtf /tmp/rtf.log

  watch-rtf <rtf_log>
      Tail <rtf_log> and print a live ⚠ warning whenever RTF < 0.5
      for two consecutive samples.
      Usage:
          python3 wandering_metrics.py watch-rtf /tmp/rtf.log

  compare <label:log_path> [<label:log_path> ...] [<out_dir>]
      Parse one or more wandering_run.sh output logs (each prefixed with a
      short label), extract metrics, and print a side-by-side comparison
      table.  The last argument is treated as an output directory if it does
      NOT contain a colon (:).  Optionally saves a summary CSV there.

      Examples (2 runs):
          python3 wandering_metrics.py compare \\
              "Headless:headless.log" "GUI:gui.log" /tmp/out

      Examples (4 runs):
          python3 wandering_metrics.py compare \\
              "Headless+Stock:hl_stock.log" \\
              "Headless+Fast:hl_fast.log"  \\
              "GUI+Stock:gui_stock.log"     \\
              "GUI+Fast:gui_fast.log"       \\
              /tmp/out
"""

import sys
import os
import re
import time


# ── sample-rtf ────────────────────────────────────────────────────────────────

def cmd_sample_rtf(rtf_log: str) -> None:
    """Read ros2 topic echo /clock from stdin; write RTF floats to rtf_log."""
    prev_sim: float | None = None
    prev_wall: float | None = None
    sec: int | None = None

    with open(rtf_log, "a", buffering=1) as fout:
        for raw in sys.stdin:
            s = raw.strip()
            if s.startswith("sec:"):
                try:
                    sec = int(s.split(":", 1)[1])
                except ValueError:
                    pass
            elif s.startswith("nanosec:") and sec is not None:
                try:
                    sim  = sec + int(s.split(":", 1)[1]) / 1e9
                    wall = time.time()
                    if prev_sim is not None:
                        dsim  = sim  - prev_sim
                        dwall = wall - prev_wall  # type: ignore[operator]
                        if dwall >= 0.5 and dsim >= 0:
                            fout.write(f"{dsim / dwall:.4f}\n")
                            prev_sim, prev_wall = sim, wall
                    else:
                        prev_sim, prev_wall = sim, wall
                except (ValueError, ZeroDivisionError):
                    pass
                sec = None


# ── watch-rtf ────────────────────────────────────────────────────────────────

def cmd_watch_rtf(rtf_log: str) -> None:
    """Tail rtf_log and print a throttle warning on two consecutive low samples."""
    # Wait until the file exists
    while not os.path.exists(rtf_log):
        time.sleep(0.5)

    below = 0
    with open(rtf_log, "r") as fin:
        # Seek to end so we only see new lines
        fin.seek(0, 2)
        while True:
            line = fin.readline()
            if not line:
                time.sleep(0.1)
                continue
            try:
                val = float(line.strip())
            except ValueError:
                continue
            if val < 0.5:
                below += 1
                if below >= 2:
                    print(
                        f"  \u26a0 THROTTLE WARNING: RTF={val:.4f}"
                        " (sim running slower than real-time)",
                        flush=True,
                    )
                    below = 0
            else:
                below = 0


# ── compare ──────────────────────────────────────────────────────────────────

def _extract_goals(text: str) -> str:
    m = re.search(r"Goals reached\s*:\s*(\S+)", text)
    return m.group(1) if m else "N/A"


def _extract_elapsed(text: str) -> str:
    m = re.search(r"Elapsed\s*:\s*(\S+)", text)
    return m.group(1) if m else "N/A"


def _extract_rtf(text: str) -> dict:
    """Return avg/min/max/throttled from the last RTF snapshot block."""
    avg = min_ = max_ = "N/A"
    # Match lines like: avg=0.971  min=0.015  max=1.006  samples=87
    for m in re.finditer(r"avg=([\d.]+)\s+min=([\d.]+)\s+max=([\d.]+)", text):
        avg, min_, max_ = m.group(1), m.group(2), m.group(3)

    throttled = "0"
    for m in re.finditer(r"(\d+) throttled sample", text):
        throttled = m.group(1)

    return {"avg": avg, "min": min_, "max": max_, "throttled": throttled}


def _extract_hz(text: str, topic: str) -> str:
    """Return the last 'average rate' value seen after the topic heading."""
    val = "N/A"
    in_section = False
    for line in text.splitlines():
        if topic in line:
            in_section = True
        if in_section and "average rate:" in line:
            parts = line.split(":")
            if len(parts) >= 2:
                val = parts[-1].strip()
            in_section = False
    return val


def _verdict(throttled: str) -> str:
    return "\u2705 none" if throttled == "0" else f"\u26a0 {throttled} sample(s)"


def cmd_compare(labeled_logs: list[tuple[str, str]], out_dir: str | None = None) -> None:
    """Print a side-by-side comparison table for any number of labeled run logs.

    Parameters
    ----------
    labeled_logs : list of (label, log_path) tuples
    out_dir      : optional directory to save comparison.csv
    """
    texts: list[str] = []
    labels: list[str] = []
    for label, path in labeled_logs:
        with open(path) as f:
            texts.append(f.read())
        labels.append(label)

    rtfs = [_extract_rtf(t) for t in texts]

    # Build row data: list of (row_label, [col_value, ...])
    row_defs = [
        ("Goals reached",              [_extract_goals(t)   for t in texts]),
        ("Elapsed time",               [_extract_elapsed(t) for t in texts]),
        ("RTF average",                [r["avg"]            for r in rtfs]),
        ("RTF min",                    [r["min"]            for r in rtfs]),
        ("RTF max",                    [r["max"]            for r in rtfs]),
        ("Throttled (RTF<0.5)",        [_verdict(r["throttled"]) for r in rtfs]),
        ("/camera/image_raw Hz",       [_extract_hz(t, "/camera/image_raw") for t in texts]),
        ("/cmd_vel_nav Hz",            [_extract_hz(t, "/cmd_vel_nav")      for t in texts]),
        ("/plan Hz",                   [_extract_hz(t, "/plan")             for t in texts]),
    ]

    # Column widths
    n = len(labels)
    LABEL_W = 26
    COL_W = max(15, max(len(lb) for lb in labels) + 2)

    total_w = LABEL_W + (COL_W + 2) * n + 2

    print()
    print("\u2554" + "\u2550" * total_w + "\u2557")
    title = f"  COMPARISON RESULTS ({n} runs)"
    print("\u2551" + title.ljust(total_w) + "\u2551")
    print("\u255a" + "\u2550" * total_w + "\u255d")

    # Header row
    fmt_parts = [f"{{:<{LABEL_W}}}"] + [f"{{:<{COL_W}}}"] * n
    fmt = "  " + "  ".join(fmt_parts)
    print(fmt.format("Metric", *labels))
    print(fmt.format("\u2500" * LABEL_W, *["\u2500" * COL_W] * n))

    for row_label, values in row_defs:
        print(fmt.format(row_label, *values))
    print()

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        csv_path = os.path.join(out_dir, "comparison.csv")
        with open(csv_path, "w") as f:
            f.write("metric," + ",".join(labels) + "\n")
            for row_label, values in row_defs:
                f.write(row_label + "," + ",".join(values) + "\n")
        print(f"  Summary CSV saved to: {csv_path}")

    print(f"  Full run logs: {out_dir or os.path.dirname(labeled_logs[0][1])}")
    print()


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "sample-rtf":
        if len(sys.argv) < 3:
            print("Usage: sample-rtf <rtf_log>", file=sys.stderr)
            sys.exit(1)
        cmd_sample_rtf(sys.argv[2])

    elif cmd == "watch-rtf":
        if len(sys.argv) < 3:
            print("Usage: watch-rtf <rtf_log>", file=sys.stderr)
            sys.exit(1)
        cmd_watch_rtf(sys.argv[2])

    elif cmd == "compare":
        # Args: one or more "label:path" strings, optional trailing out_dir (no colon)
        rest = sys.argv[2:]
        if not rest:
            print("Usage: compare <label:log_path> [<label:log_path> ...] [out_dir]",
                  file=sys.stderr)
            sys.exit(1)

        # Determine if the last arg is an out_dir (no colon) or another label:path
        out_dir = None
        if rest and ":" not in rest[-1]:
            out_dir = rest[-1]
            rest = rest[:-1]

        if not rest:
            print("Error: no label:path arguments provided", file=sys.stderr)
            sys.exit(1)

        labeled_logs: list[tuple[str, str]] = []
        for arg in rest:
            if ":" not in arg:
                print(f"Error: expected 'label:path' but got: {arg!r}", file=sys.stderr)
                sys.exit(1)
            label, _, path = arg.partition(":")
            labeled_logs.append((label, path))

        cmd_compare(labeled_logs, out_dir)

    else:
        print(f"Unknown subcommand: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
