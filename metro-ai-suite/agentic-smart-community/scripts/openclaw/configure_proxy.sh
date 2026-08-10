#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Configure or clear the HTTP(S) proxy used by the OpenClaw gateway service.
# Only the gateway's own systemd environment is touched - the system/shell
# proxy configuration is never modified.

set -euo pipefail

UNIT="${OPENCLAW_SYSTEMD_UNIT:-openclaw-gateway.service}"
DROPIN_DIR="${HOME}/.config/systemd/user/${UNIT}.d"
DROPIN="${DROPIN_DIR}/proxy.conf"
LOCAL_NO_PROXY="localhost,127.0.0.1,::1"
SKIP_RESTART="${SKIP_RESTART:-0}"

usage() {
	cat <<EOF
Usage: bash $(basename "$0") [configure|clear|status]

  configure  Point the OpenClaw gateway at an HTTP(S) proxy. Values are taken
             from the existing drop-in, then from the current shell env
             (http_proxy / https_proxy / no_proxy); anything still missing is
             asked for interactively.
  clear      Remove the proxy from the gateway only. System proxy untouched.
  status     Show the configured drop-in and the running gateway's proxy env.

Env: SKIP_RESTART=1 to write the drop-in without restarting the gateway.
EOF
}

command -v systemctl >/dev/null 2>&1 || { echo "ERROR: systemctl not found; this script targets systemd user services." >&2; exit 1; }
systemctl --user cat "$UNIT" >/dev/null 2>&1 || {
	echo "ERROR: unit '$UNIT' not found. Install the gateway first: openclaw onboard --install-daemon" >&2
	exit 1
}

dropin_get() {
	[[ -f "$DROPIN" ]] || return 0
	sed -n "s/^Environment=\"\?$1=\([^\"]*\)\"\?$/\1/p" "$DROPIN" | head -n1
}

restart_gateway() {
	systemctl --user daemon-reload
	if [[ "$SKIP_RESTART" == "1" ]]; then
		echo "==> SKIP_RESTART=1; gateway restart skipped (run 'systemctl --user restart $UNIT' to apply)"
		return
	fi
	echo "==> Restarting $UNIT"
	systemctl --user restart "$UNIT"
	sleep 2
}

show_status() {
	echo "==> Drop-in: $DROPIN"
	if [[ -f "$DROPIN" ]]; then
		sed 's/^/    /' "$DROPIN"
	else
		echo "    (absent - gateway runs without a proxy)"
	fi

	local pid
	pid="$(systemctl --user show -p MainPID --value "$UNIT" 2>/dev/null || echo 0)"
	echo "==> Running gateway (PID ${pid:-0}) proxy env:"
	if [[ "${pid:-0}" =~ ^[0-9]+$ ]] && [[ "${pid:-0}" -gt 0 ]] && [[ -r "/proc/$pid/environ" ]]; then
		local env_out
		env_out="$(tr '\0' '\n' <"/proc/$pid/environ" | grep -i '_proxy=' | sort || true)"
		[[ -n "$env_out" ]] && sed 's/^/    /' <<<"$env_out" || echo "    (none)"
	else
		echo "    (gateway not running)"
	fi
}

do_configure() {
	local http_p https_p no_p
	http_p="$(dropin_get http_proxy)"
	https_p="$(dropin_get https_proxy)"
	no_p="$(dropin_get no_proxy)"

	[[ -n "$http_p" ]] || http_p="${http_proxy:-${HTTP_PROXY:-}}"
	[[ -n "$https_p" ]] || https_p="${https_proxy:-${HTTPS_PROXY:-}}"
	[[ -n "$no_p" ]] || no_p="${no_proxy:-${NO_PROXY:-}}"

	if [[ -z "$http_p" && -z "$https_p" ]]; then
		[[ -t 0 ]] || { echo "ERROR: no proxy found in the drop-in or the environment, and stdin is not a TTY." >&2; exit 1; }
		echo "No proxy found in the gateway drop-in or the current shell environment."
		read -r -p "HTTP proxy URL (e.g. http://proxy.example.com:911): " http_p
		[[ -n "$http_p" ]] || { echo "ERROR: an HTTP proxy URL is required." >&2; exit 1; }
		read -r -p "HTTPS proxy URL [${http_p}]: " https_p
		read -r -p "no_proxy [${LOCAL_NO_PROXY}]: " no_p
	fi

	[[ -n "$https_p" ]] || https_p="$http_p"
	[[ -n "$http_p" ]] || http_p="$https_p"
	no_p="${no_p:-$LOCAL_NO_PROXY}"

	# Local model / MCP endpoints must always bypass the proxy.
	local entry
	for entry in ${LOCAL_NO_PROXY//,/ }; do
		[[ ",$no_p," == *",$entry,"* ]] || no_p="${no_p},${entry}"
	done

	echo "==> Writing $DROPIN"
	echo "    http_proxy  = $http_p"
	echo "    https_proxy = $https_p"
	echo "    no_proxy    = $no_p"
	mkdir -p "$DROPIN_DIR"
	cat >"$DROPIN" <<EOF
# Managed by configure_proxy.sh - gateway-only proxy, system proxy untouched.
[Service]
Environment="http_proxy=${http_p}"
Environment="HTTP_PROXY=${http_p}"
Environment="https_proxy=${https_p}"
Environment="HTTPS_PROXY=${https_p}"
Environment="no_proxy=${no_p}"
Environment="NO_PROXY=${no_p}"
EOF

	restart_gateway
	show_status
	echo "==> Done. Verify with: openclaw agent --session-key proxy-check -m 'web_search for openclaw and give me one title'"
}

do_clear() {
	if [[ -f "$DROPIN" ]]; then
		echo "==> Removing $DROPIN"
		rm -f "$DROPIN"
		rmdir "$DROPIN_DIR" 2>/dev/null || true
		restart_gateway
	else
		echo "==> No proxy drop-in found; nothing to clear."
	fi
	show_status
	echo "==> Gateway proxy cleared. System / shell proxy settings were not modified."
}

action="${1:-}"
if [[ -z "$action" ]]; then
	[[ -t 0 ]] || { usage >&2; exit 1; }
	echo "OpenClaw gateway proxy"
	echo "  1) configure"
	echo "  2) clear"
	echo "  3) status"
	read -r -p "Select [1]: " choice
	case "${choice:-1}" in
	1) action="configure" ;;
	2) action="clear" ;;
	3) action="status" ;;
	*) echo "ERROR: invalid selection." >&2; exit 1 ;;
	esac
fi

case "$action" in
configure) do_configure ;;
clear) do_clear ;;
status) show_status ;;
-h | --help | help) usage ;;
*)
	echo "ERROR: unknown action '$action'" >&2
	usage >&2
	exit 1
	;;
esac
