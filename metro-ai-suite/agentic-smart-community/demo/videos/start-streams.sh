#!/usr/bin/env bash
# Start RTSP push for each enabled stream declared in a streams config.
#
# The default config lives with the rest of the demo resources in
# ../quick-start/streams.yaml. Point STREAMS_CONFIG at another file to publish a
# different set of streams (see demo/user-case-register/streams.elder_care.yaml).
#
# Usage:
#   ./start-streams.sh                 # start every enabled stream
#   ./start-streams.sh cam_fridge ...  # start only the named streams (still must be enabled)
#   ./start-streams.sh --stop          # kill all running pushers
#   ./start-streams.sh --status        # show running PIDs
#
# Each ffmpeg runs in the background; PIDs and logs go under .run/.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${STREAMS_CONFIG:-$SCRIPT_DIR/../quick-start/streams.yaml}"
RUN_DIR="$SCRIPT_DIR/.run"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
PYTHON_BIN="$VENV_DIR/bin/python"
ACTIVE_STREAMS_FILE="$RUN_DIR/active-streams.txt"
mkdir -p "$RUN_DIR"

command -v ffmpeg >/dev/null || { echo "ffmpeg not found in PATH" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 not found in PATH" >&2; exit 1; }
[[ -f "$CONFIG_FILE" ]] || { echo "config not found: $CONFIG_FILE" >&2; exit 1; }

# Relative `file:` entries resolve against the config's own directory, so a
# config can sit anywhere and still point at videos next to it.
CONFIG_DIR="$(cd "$(dirname "$CONFIG_FILE")" && pwd)"

ensure_python_env() {
  if [[ ! -d "$VENV_DIR" ]]; then
    echo "creating Python virtualenv: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
  fi

  if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "virtualenv python not found: $PYTHON_BIN" >&2
    exit 1
  fi

  if [[ -f "$REQUIREMENTS_FILE" ]]; then
    "$PYTHON_BIN" -m pip install -q -r "$REQUIREMENTS_FILE"
  fi
}

parse_streams() {
  # Emit one unit-separator-delimited row per stream. Bash collapses empty fields
  # when IFS uses whitespace such as tabs, but an unset ${VAR} must stay empty.
  "$PYTHON_BIN" - "$CONFIG_FILE" <<'PY'
import os
import re
import sys

import yaml

ENV_VAR = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}", re.IGNORECASE)


def expand_env(value):
    if not isinstance(value, str):
        return "", []
    names = ENV_VAR.findall(value)
    missing = [name for name in names if not os.environ.get(name)]
    return ENV_VAR.sub(lambda match: os.environ.get(match.group(1), ""), value), missing


with open(sys.argv[1]) as f:
    cfg = yaml.safe_load(f) or {}
for sid, s in (cfg.get("streams") or {}).items():
    enabled = bool(s.get("enabled", False))
    file, missing = expand_env(s.get("file", ""))
    rtsp = s.get("rtsp_url", "")
    loop = bool(s.get("loop", False))
    print("\x1f".join((sid, str(enabled), file, rtsp, str(loop), ",".join(missing))))
PY
}

write_mediamtx_conf() {
  # Read mediamtx.binary and mediamtx.config from the streams config, expand ~ in
  # binary path, dump mediamtx.config sub-tree to a temp YAML file.
  # Emit a single tab-separated row: binary\tconf_path
  "$PYTHON_BIN" - "$CONFIG_FILE" "$RUN_DIR/_mediamtx.yml" <<'PY'
import os, sys, yaml
cfg_path, out_path = sys.argv[1], sys.argv[2]
with open(cfg_path) as f:
    cfg = yaml.safe_load(f) or {}
m = cfg.get("mediamtx") or {}
binary = os.path.expanduser(m.get("binary", ""))
conf = m.get("config") or {}
with open(out_path, "w") as f:
    yaml.safe_dump(conf, f, sort_keys=False)
print(f"{binary}\t{out_path}")
PY
}

start_mediamtx() {
  IFS=$'\t' read -r mm_bin mm_conf < <(write_mediamtx_conf)

  local pidfile="$RUN_DIR/_mediamtx.pid"
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "  mediamtx already running (pid $(cat "$pidfile"))"
    return 0
  fi
  rm -f "$pidfile"

  if [[ -z "$mm_bin" || ! -x "$mm_bin" ]]; then
    echo "  mediamtx binary not found or not executable: $mm_bin" >&2
    return 1
  fi

  local logfile="$RUN_DIR/_mediamtx.log"
  nohup "$mm_bin" "$mm_conf" >"$logfile" 2>&1 &
  local pid=$!
  echo "$pid" >"$pidfile"

  # Give RTSP listener a moment to bind before pushers connect.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if ss -tln 2>/dev/null | grep -q ':8554 '; then
      break
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "  mediamtx exited during startup — see $logfile" >&2
      rm -f "$pidfile"
      return 1
    fi
    sleep 0.2
  done
  echo "  started mediamtx (pid $pid)"
}

stop_one() {
  local sid="$1"
  local pidfile="$RUN_DIR/$sid.pid"
  [[ -f "$pidfile" ]] || return 0
  local pid
  pid="$(cat "$pidfile")"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.2
    done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    echo "stopped $sid (pid $pid)"
  fi
  rm -f "$pidfile"
}

cmd_stop() {
  exec "$SCRIPT_DIR/stop_streams.sh"
}

cmd_status() {
  shopt -s nullglob
  local any=0
  for pidfile in "$RUN_DIR"/*.pid; do
    any=1
    local sid pid
    sid="$(basename "$pidfile" .pid)"
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "  $sid	pid=$pid	running"
    else
      echo "  $sid	pid=$pid	dead (stale pidfile)"
    fi
  done
  [[ $any -eq 0 ]] && echo "  (no pidfiles in $RUN_DIR)"
}

start_one() {
  local sid="$1" file="$2" rtsp="$3" loop="$4"
  if [[ -z "$file" ]]; then
    echo "  warning: skip $sid: video path is empty" >&2
    return 1
  fi
  local abs_file="$file"
  [[ "$abs_file" != /* ]] && abs_file="$CONFIG_DIR/$file"
  if [[ ! -f "$abs_file" ]]; then
    echo "  warning: skip $sid: video file not found: $abs_file" >&2
    return 1
  fi

  local pidfile="$RUN_DIR/$sid.pid"
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "  $sid already running (pid $(cat "$pidfile"))"
    return 0
  fi
  rm -f "$pidfile"

  local logfile="$RUN_DIR/$sid.log"
  local ffargs=()
  [[ "$loop" == "True" ]] && ffargs+=(-stream_loop -1)
  ffargs+=(-re -i "$abs_file" -c copy -f rtsp -rtsp_transport tcp "$rtsp")

  nohup ffmpeg -hide_banner -loglevel warning "${ffargs[@]}" >"$logfile" 2>&1 &
  local pid=$!
  echo "$pid" >"$pidfile"
  echo "  started $sid (pid $pid) -> $rtsp"
}

# Argument parsing
case "${1:-}" in
  --stop) cmd_stop; exit 0 ;;
  --status) cmd_status; exit 0 ;;
  -h|--help)
    sed -n '2,14p' "$0"
    exit 0 ;;
esac

# Optional positional filter: only start these stream IDs
declare -A WANTED=()
for arg in "$@"; do WANTED["$arg"]=1; done
filter_active=$(( ${#WANTED[@]} > 0 ))

ensure_python_env

start_mediamtx || true

# This invocation defines the monitor set that start-demo.sh will register.
: >"$ACTIVE_STREAMS_FILE"

started=0
skipped=0
while IFS=$'\x1f' read -r sid enabled file rtsp loop missing_vars; do
  [[ -z "$sid" ]] && continue
  if (( filter_active )) && [[ -z "${WANTED[$sid]:-}" ]]; then
    continue
  fi
  if [[ "$enabled" != "True" ]]; then
    echo "  skip $sid: enabled=false"
    skipped=$((skipped+1))
    continue
  fi
  if [[ -n "$missing_vars" ]]; then
    echo "  warning: skip $sid: required video variable is unset or empty: $missing_vars" >&2
    skipped=$((skipped+1))
    continue
  fi
  if start_one "$sid" "$file" "$rtsp" "$loop"; then
    printf '%s\n' "$sid" >>"$ACTIVE_STREAMS_FILE"
    started=$((started+1))
  else
    skipped=$((skipped+1))
  fi
done < <(parse_streams)

echo
echo "summary: started=$started skipped=$skipped (logs: $RUN_DIR/<id>.log)"
echo "active streams: $ACTIVE_STREAMS_FILE"
