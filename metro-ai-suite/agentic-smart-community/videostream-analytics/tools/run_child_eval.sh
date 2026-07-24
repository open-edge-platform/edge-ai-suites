#!/usr/bin/env bash
# Thin wrapper around run_eval.sh for the child scenario.
# Use `run_eval.sh --scenario child` directly going forward — see tools/README.md.
exec "$(dirname "$0")/run_eval.sh" --scenario child "$@"
