#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║              OpenClaw uninstall (clean, demo-free)               ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  Removes a plain OpenClaw install — nothing demo-specific.        ║
# ║                                                                  ║
# ║  Steps:                                                          ║
# ║    1. stop the gateway            (openclaw gateway stop)         ║
# ║    2. openclaw uninstall          (remove user systemd daemon +  ║
# ║                                    ~/.openclaw runtime files)     ║
# ║    3. strip the OpenClaw bash-completion source line from        ║
# ║       ~/.bashrc                                                  ║
# ║    4. remove the 'openclaw' npm CLI itself                       ║
# ║                                                                  ║
# ║  With -y the npm CLI is removed too (npm uninstall -g openclaw). ║
# ║  Without -y, step 4 asks first.                                 ║
# ║                                                                  ║
# ║  Usage:                                                          ║
# ║    bash uninstall.sh          # interactive (asks about CLI)     ║
# ║    bash uninstall.sh -y       # no prompts, also removes the CLI ║
# ╚══════════════════════════════════════════════════════════════════╝
set -uo pipefail

OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
BASHRC="$HOME/.bashrc"
YES=false
for arg in "$@"; do
  case "$arg" in
    -y|--yes) YES=true ;;
    -h|--help) sed -n '2,21p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; echo "Usage: bash uninstall.sh [-y|--yes]" >&2; exit 1 ;;
  esac
done

info() { echo "[ ok ] $*"; }
warn() { echo "[warn] $*"; }
title(){ echo ""; echo ">>> $*"; }

cat <<EOF

==========================================
  OpenClaw uninstall (clean)
==========================================

This will:
  1. Stop the gateway                     (openclaw gateway stop)
  2. Run 'openclaw uninstall'             (remove user systemd daemon + $OPENCLAW_HOME)
  3. Remove the bash-completion source line from $BASHRC
$($YES && echo "  4. Remove the 'openclaw' npm CLI        (npm uninstall -g openclaw)" || echo "  4. Remove the 'openclaw' npm CLI        (asks first)")

EOF

if ! $YES; then
  read -r -p "Proceed? [y/N] " ans
  case "$ans" in [Yy]|[Yy][Ee][Ss]) ;; *) echo "Aborted."; exit 0 ;; esac
fi

# ─── Step 1: stop the gateway ───────────────────────────────────────
title "Step 1: stop the gateway"
if command -v openclaw >/dev/null 2>&1; then
  openclaw gateway stop 2>/dev/null && info "Gateway stopped" || warn "Gateway not running (continuing)"
else
  warn "openclaw CLI not found on PATH — skipping"
fi

# ─── Step 2: openclaw uninstall ─────────────────────────────────────
title "Step 2: openclaw uninstall"
if command -v openclaw >/dev/null 2>&1; then
  # Back up the config so a broken/invalid config can't make uninstall fail.
  if [[ -f "$OPENCLAW_HOME/openclaw.json" ]]; then
    BAK_CONFIG="$OPENCLAW_HOME/openclaw.json.uninstall-backup.$(date +%s)"
    cp -f "$OPENCLAW_HOME/openclaw.json" "$BAK_CONFIG" 2>/dev/null \
      && info "Backed up config to $BAK_CONFIG"
  fi

  # If `openclaw uninstall` fails (commonly config validation), tear down manually.
  if ! openclaw uninstall 2>&1; then
    warn "openclaw uninstall failed — cleaning up manually"
    openclaw gateway stop 2>/dev/null || true
    if systemctl --user list-unit-files 2>/dev/null | grep -q openclaw-gateway; then
      systemctl --user disable openclaw-gateway 2>/dev/null || true
      systemctl --user stop openclaw-gateway 2>/dev/null || true
    fi
    if [[ -d "$OPENCLAW_HOME" ]]; then
      rm -rf "$OPENCLAW_HOME" && info "Removed $OPENCLAW_HOME"
    fi
  fi
else
  warn "openclaw CLI not found on PATH — skipping"
fi

# ─── Step 3: scrub bash-completion line from ~/.bashrc ──────────────
title "Step 3: clean ~/.bashrc completion line"
if [[ -f "$BASHRC" ]]; then
  COMPLETION_PATH="$OPENCLAW_HOME/completions/openclaw.bash"
  if grep -qF "$COMPLETION_PATH" "$BASHRC" || grep -qF "# OpenClaw Completion" "$BASHRC"; then
    BAK="$BASHRC.uninstall-openclaw.bak.$(date +%s)"
    cp -f "$BASHRC" "$BAK"
    ESC_PATH=$(printf '%s' "$COMPLETION_PATH" | sed 's|/|\\/|g')
    sed -i \
      -e '/^# OpenClaw Completion$/d' \
      -e "/^source \"${ESC_PATH}\"$/d" \
      "$BASHRC"
    info "Stripped bash-completion entry from $BASHRC (backup: $BAK)"
  else
    info "No OpenClaw bash-completion entry in $BASHRC — nothing to strip"
  fi
else
  warn "$BASHRC not found — skipping"
fi

# ─── Step 4: remove the npm CLI ─────────────────────────────────────
# With -y remove it directly; without -y, ask first.
title "Step 4: remove the 'openclaw' npm CLI"
purge_cli=$YES
if ! $YES; then
  read -r -p "Also remove the 'openclaw' npm CLI (npm uninstall -g openclaw)? [y/N] " ans
  case "$ans" in [Yy]|[Yy][Ee][Ss]) purge_cli=true ;; esac
fi
if $purge_cli; then
  if command -v npm >/dev/null 2>&1; then
    npm uninstall -g openclaw && info "Removed the 'openclaw' npm CLI" \
      || warn "npm uninstall -g openclaw failed (removed already? or needs sudo)"
  else
    warn "npm not found on PATH — cannot remove the CLI"
  fi
else
  info "Keeping the 'openclaw' npm CLI"
fi

cat <<EOF

==========================================
  OpenClaw uninstall finished.
==========================================

Verify:
  - 'openclaw gateway status'   reports not running / not installed
  - ls $OPENCLAW_HOME            is empty or absent
  - new shell: no error about missing openclaw.bash completion

To reinstall:  see README.md in this directory
EOF
