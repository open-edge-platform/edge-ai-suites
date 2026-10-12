#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Runs as root only long enough to fix ownership of the bind-mounted segments
# directory, then drops to the non-root `appuser` for the actual app process.
#
# Why this is needed: HOST_SEGMENTS_DIR (compose.yaml) can point at a host
# directory or a tmpfs path like /dev/shm/<name>. Docker auto-creates that
# path as root if it doesn't already exist, and tmpfs mounts reset to root
# ownership on every host reboot. appuser (uid 1000) then can't write
# segments, which previously made the segment writer fail with
# "Permission denied" on every stream connection.
set -euo pipefail

SEGMENT_DIR="${SEGMENT_OUTPUT_DIR:-segments}"
case "$SEGMENT_DIR" in
    /*) : ;;                      # already absolute
    *) SEGMENT_DIR="/app/${SEGMENT_DIR}" ;;
esac

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$SEGMENT_DIR"
    if ! chown -R appuser:appuser "$SEGMENT_DIR" 2>/dev/null; then
        echo "entrypoint: warning: could not chown '${SEGMENT_DIR}' (continuing; segment writing may fail until fixed on the host)" >&2
    fi

    # setpriv changes uid/gid but preserves environment; reset home-related
    # variables so libraries do not keep trying to write under /root.
    export HOME=/home/appuser
    export XDG_CONFIG_HOME="$HOME/.config"
    export XDG_CACHE_HOME="$HOME/.cache"
    mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME"
    chown -R appuser:appuser "$HOME" 2>/dev/null || true

    # Drop to appuser for the actual app process. `--keep-groups` would also
    # keep root's own group (gid 0) as a supplementary group on the app
    # process, which we don't want. Instead, explicitly carry over only the
    # extra numeric supplementary groups Docker injected via `group_add`
    # (e.g. the render group for /dev/dri GPU/NPU access), dropping gid 0.
    extra_groups=$(id -G | tr ' ' '\n' | grep -v '^0$' | paste -sd, -)
    if [ -n "$extra_groups" ]; then
        exec setpriv --reuid=appuser --regid=appuser --groups="$extra_groups" -- "$@"
    else
        exec setpriv --reuid=appuser --regid=appuser --clear-groups -- "$@"
    fi
fi

# Already running as non-root (e.g. `docker run --user`) — nothing to fix.
exec "$@"
