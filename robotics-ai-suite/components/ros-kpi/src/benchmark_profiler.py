#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
r"""
benchmark_profiler.py — Load and query a benchmark run profile YAML config.

Used by run scripts to externalize the ROS 2 launch command and bag topic
list so users can customise their scenario without editing shell scripts.

YAML schema (config/<scenario>_run.yaml)
-----------------------------------------
  launch:
    cmd: "ros2 launch <pkg> <launch_file>"   # scenario derived from <pkg>
    args: []                                  # extra args appended to cmd
    init_sleep: 12                            # seconds to wait after launch
  stop:
    goal_pattern: "Goal was reached"          # grep pattern for goal counting
    goal_count: 0                             # stop after N goals (0=Ctrl-C)
    timeout: 0                                # hard timeout seconds (0=off)
    done_pattern: ""                          # stop when this string appears
    task_pattern: ""                          # pattern to count tasks (summary)
  monitor:
    graph_only: false                         # pass --graph-only to monitor_stack
  gazebo:
    press_play: false                         # send gz WorldControl play call
  cleanup:
    sweep: "ros2 |gz sim|..."                 # pkill -f pattern for cleanup
  session:
    output_subdir: ""                         # under monitoring_sessions/ (derived)
    log_prefix: ""                            # log file prefix (derived)
    record_log: ""                            # /tmp/<prefix>_record.log (derived)
  bag:
    topics: [...]                             # topics for ros2 bag record

CLI usage (from bash run scripts)
----------------------------------
  # Source all CONF_* variables in one shot (used by benchmark_runner.sh)
  eval "$(uv run python src/benchmark_profiler.py --config config/wandering_run.yaml --export-bash)"

  # Individual field queries
  TOPICS=$(uv run python src/benchmark_profiler.py --config config/wandering_run.yaml --topics)
  LAUNCH=$(uv run python src/benchmark_profiler.py --config config/wandering_run.yaml --launch-cmd)
  SLEEP=$( uv run python src/benchmark_profiler.py --config config/wandering_run.yaml --init-sleep)
  uv run python src/benchmark_profiler.py --config config/wandering_run.yaml --show

Module usage
------------
  from benchmark_profiler import RunConfig
  cfg = RunConfig.load("config/wandering_run.yaml")
  print(cfg.launch_cmd)     # "ros2 launch wandering_gazebo_tutorial ..."
  print(cfg.bag_topics)     # ["/scan", "/imu", ...]
  print(cfg.export_bash())  # shell-sourceable CONF_* assignments
"""

from __future__ import annotations

import argparse
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml

_DEFAULT_SWEEP = (
    "ros2 |gz sim|gz_server|gz server"
    "|/opt/ros/[a-z]*/lib/|gazebo|rtabmap|nav2|turtlebot|rviz2"
)


@dataclass
class RunConfig:
    """Parsed and validated run profile loaded from a YAML config file."""

    # ── launch ────────────────────────────────────────────────────────────────
    scenario: str
    launch_cmd: str
    launch_args: List[str] = field(default_factory=list)
    init_sleep: int = 12

    # ── stop / termination ────────────────────────────────────────────────────
    goal_pattern: str = ""    # grep pattern counted for goal-based stopping
    goal_count: int = 0       # stop when count reaches this (0 = ignore)
    timeout: int = 0          # hard stop after N seconds (0 = off)
    done_pattern: str = ""    # stop when this literal string appears in log
    task_pattern: str = ""    # grep pattern counted for summary only

    # ── monitoring / gazebo ───────────────────────────────────────────────────
    graph_only: bool = False   # pass --graph-only to monitor_stack.py
    press_play: bool = False   # send gz WorldControl play service after init

    # ── launch env overrides ─────────────────────────────────────────────────
    launch_env: dict = field(default_factory=dict)

    # ── cleanup / session ─────────────────────────────────────────────────────
    sweep: str = _DEFAULT_SWEEP
    log_prefix: str = ""
    output_subdir: str = ""
    record_log: str = ""

    # ── post-run analysis ─────────────────────────────────────────────────────
    post_run_cmd: str = ""   # command to run after the run; SESSION_DIR is substituted

    # ── bag ───────────────────────────────────────────────────────────────────
    bag_topics: List[str] = field(default_factory=list)

    # ── Constructors ──────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: str | Path) -> "RunConfig":
        """Load and validate a run profile YAML file.

        Parameters
        ----------
        path:
            Path to the YAML config file.

        Returns
        -------
        RunConfig
            Validated config object.

        Raises
        ------
        FileNotFoundError
            If the config file does not exist.
        ValueError
            If required fields are missing or the file is malformed.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Run config not found: {p}")

        with p.open() as fh:
            data = yaml.safe_load(fh)

        if not isinstance(data, dict):
            raise ValueError(f"Run config must be a YAML mapping: {p}")

        # ── launch ───────────────────────────────────────────────────────────
        launch = data.get("launch") or {}
        launch_cmd = launch.get("cmd")
        if not launch_cmd:
            raise ValueError(f"Run config missing required field 'launch.cmd': {p}")
        launch_args = [str(a) for a in (launch.get("args") or [])]
        init_sleep = int(launch.get("init_sleep", 12))
        if init_sleep < 0:
            raise ValueError(f"'launch.init_sleep' must be >= 0, got {init_sleep}: {p}")

        # ── scenario — derived from the ROS package name in launch.cmd ────────
        # Expected format: "ros2 launch <package> <launch_file> [args...]"
        tokens = str(launch_cmd).split()
        if len(tokens) >= 3 and tokens[:2] == ["ros2", "launch"]:
            scenario = tokens[2]
        else:
            # Fallback: use config file stem stripped of "_run" suffix
            scenario = p.stem.replace("_run", "")

        # ── stop / termination ────────────────────────────────────────────────
        stop = data.get("stop") or {}
        goal_pattern = str(stop.get("goal_pattern") or "")
        goal_count   = int(stop.get("goal_count", 0))
        timeout      = int(stop.get("timeout", 0))
        done_pattern = str(stop.get("done_pattern") or "")
        task_pattern = str(stop.get("task_pattern") or "")

        # ── launch env overrides ──────────────────────────────────────────────
        launch_env = {str(k): str(v) for k, v in (launch.get("env") or {}).items()}

        # ── monitoring / gazebo ───────────────────────────────────────────────
        monitor    = data.get("monitor") or {}
        graph_only = bool(monitor.get("graph_only", False))
        gazebo     = data.get("gazebo") or {}
        press_play = bool(gazebo.get("press_play", False))

        # ── cleanup ───────────────────────────────────────────────────────────
        cleanup = data.get("cleanup") or {}
        sweep   = str(cleanup.get("sweep") or _DEFAULT_SWEEP)

        # ── session (derive from scenario if not set) ─────────────────────────
        session       = data.get("session") or {}
        _prefix       = scenario.split("_")[0]
        log_prefix    = str(session.get("log_prefix")    or _prefix)
        output_subdir = str(session.get("output_subdir") or _prefix)
        record_log    = str(session.get("record_log")    or f"/tmp/{log_prefix}_record.log")
        # ── post-run analysis ─────────────────────────────────────────────────
        post_run    = data.get("post_run") or {}
        post_run_cmd = str(post_run.get("cmd") or "")
        # ── bag ───────────────────────────────────────────────────────────────
        bag = data.get("bag") or {}
        bag_topics = [str(t) for t in (bag.get("topics") or [])]
        if not bag_topics:
            raise ValueError(f"Run config 'bag.topics' is empty or missing: {p}")

        return cls(
            scenario=str(scenario),
            launch_cmd=str(launch_cmd),
            launch_args=launch_args,
            init_sleep=init_sleep,
            launch_env=launch_env,
            goal_pattern=goal_pattern,
            goal_count=goal_count,
            timeout=timeout,
            done_pattern=done_pattern,
            task_pattern=task_pattern,
            graph_only=graph_only,
            press_play=press_play,
            sweep=sweep,
            log_prefix=log_prefix,
            output_subdir=output_subdir,
            record_log=record_log,
            post_run_cmd=post_run_cmd,
            bag_topics=bag_topics,
        )

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def full_launch_cmd(self) -> str:
        """Launch command with any extra args appended."""
        parts = [self.launch_cmd] + self.launch_args
        return " ".join(parts)

    @property
    def topics_as_args(self) -> str:
        """Bag topics as a space-separated string for `ros2 bag record`."""
        return " ".join(self.bag_topics)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def export_bash(self) -> str:
        """Return shell-sourceable CONF_* variable assignments for benchmark_runner.sh."""
        # Build KEY=VALUE pairs for env(1); values are unquoted here because
        # env(1) parses KEY=VALUE literally — no shell quoting needed.
        env_pairs = " ".join(f"{k}={v}" for k, v in self.launch_env.items())
        lines = [
            f"CONF_SCENARIO={shlex.quote(self.scenario)}",
            f"CONF_LAUNCH_CMD={shlex.quote(self.full_launch_cmd)}",
            f"CONF_LAUNCH_ENV={shlex.quote(env_pairs)}",
            f"CONF_INIT_SLEEP={self.init_sleep}",
            f"CONF_LOG_PREFIX={shlex.quote(self.log_prefix)}",
            f"CONF_TOPICS={shlex.quote(self.topics_as_args)}",
            f"CONF_GOAL_PATTERN={shlex.quote(self.goal_pattern)}",
            f"CONF_GOAL_COUNT={self.goal_count}",
            f"CONF_TIMEOUT={self.timeout}",
            f"CONF_DONE_PATTERN={shlex.quote(self.done_pattern)}",
            f"CONF_TASK_PATTERN={shlex.quote(self.task_pattern)}",
            f"CONF_GRAPH_ONLY={1 if self.graph_only else 0}",
            f"CONF_PRESS_PLAY={1 if self.press_play else 0}",
            f"CONF_SWEEP={shlex.quote(self.sweep)}",
            f"CONF_OUTPUT_SUBDIR={shlex.quote(self.output_subdir)}",
            f"CONF_RECORD_LOG={shlex.quote(self.record_log)}",
            f"CONF_POST_RUN_CMD={shlex.quote(self.post_run_cmd)}",
        ]
        return "\n".join(lines)

    def show(self, file=sys.stdout) -> None:
        """Print a human-readable config summary."""
        print(f"Scenario      : {self.scenario}", file=file)
        print(f"Launch cmd    : {self.full_launch_cmd}", file=file)
        if self.launch_env:
            for k, v in self.launch_env.items():
                print(f"Launch env    : {k}={v}", file=file)
        print(f"Init sleep    : {self.init_sleep}s", file=file)
        print(f"Log prefix    : {self.log_prefix}", file=file)
        print(f"Output subdir : monitoring_sessions/{self.output_subdir}/", file=file)
        if self.goal_pattern:
            print(f"Goal pattern  : {self.goal_pattern!r}  (stop at {self.goal_count or 'Ctrl-C'})", file=file)
        if self.done_pattern:
            print(f"Done pattern  : {self.done_pattern!r}", file=file)
        if self.timeout:
            print(f"Timeout       : {self.timeout}s", file=file)
        print(f"Graph only    : {self.graph_only}", file=file)
        print(f"Press play    : {self.press_play}", file=file)
        print(f"Bag topics    : {len(self.bag_topics)}", file=file)
        for topic in self.bag_topics:
            print(f"                {topic}", file=file)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="benchmark_profiler.py",
        description="Load a benchmark run profile YAML and query its fields.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Print bag topics for use in ros2 bag record\n"
            "  uv run python src/benchmark_profiler.py --config config/wandering_run.yaml --topics\n\n"
            "  # Print the launch command\n"
            "  uv run python src/benchmark_profiler.py --config config/wandering_run.yaml --launch-cmd\n\n"
            "  # Show full config summary\n"
            "  uv run python src/benchmark_profiler.py --config config/wandering_run.yaml --show\n"
        ),
    )
    p.add_argument(
        "--config", required=True, metavar="FILE",
        help="Path to the run profile YAML (e.g. config/wandering_run.yaml)",
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--export-bash", action="store_true",
        help="Print all config values as shell-sourceable CONF_* assignments",
    )
    group.add_argument(
        "--topics", action="store_true",
        help="Print bag topics as space-separated string (for ros2 bag record)",
    )
    group.add_argument(
        "--launch-cmd", action="store_true",
        help="Print the full launch command string",
    )
    group.add_argument(
        "--init-sleep", action="store_true",
        help="Print the init sleep seconds as an integer",
    )
    group.add_argument(
        "--show", action="store_true",
        help="Print a human-readable config summary",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    try:
        cfg = RunConfig.load(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.export_bash:
        print(cfg.export_bash())
    elif args.topics:
        print(cfg.topics_as_args)
    elif args.launch_cmd:
        print(cfg.full_launch_cmd)
    elif args.init_sleep:
        print(cfg.init_sleep)
    elif args.show:
        cfg.show()


if __name__ == "__main__":
    main()
