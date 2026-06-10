#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# wandering_run.sh — Thin wrapper around benchmark_runner.sh for the wandering scenario.
#
# All CLI options are forwarded to benchmark_runner.sh unchanged.
# To customise the launch command, bag topics, stop condition, or any other
# scenario behaviour, edit config/wandering_run.yaml instead of this file.
#
# Usage:
#   bash src/wandering_run.sh [--goals N] [--timeout SECS] [--record] [--plot]
#                             [--output-parent DIR] [--side-terminals]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
exec "$SCRIPT_DIR/benchmark_runner.sh" \
  --run-config "$REPO_ROOT/config/wandering_run.yaml" \
  "$@"

