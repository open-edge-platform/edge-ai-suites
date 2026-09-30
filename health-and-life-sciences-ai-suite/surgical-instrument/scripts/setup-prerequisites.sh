#!/usr/bin/env bash
# Surgical Instrument — host prerequisite installer for Ubuntu 24.04 (noble).
#
# Installs everything the Docker Compose stack and the (optional) local
# training/bootstrap flow need:
#
#   * base tools               (curl, git, python3, python3-venv, tar, make, ...)
#   * Docker Engine + Compose  (docker-ce, docker-ce-cli, docker-compose-plugin)
#   * Intel client GPU stack   (Level Zero + OpenCL + iHD VA-API, from the
#                               official intel-graphics apt repo)
#   * group membership         (render, video, docker)
#
# It is idempotent: every package/repo/group is checked before it is added.
#
# Usage (from the surgical-instrument project root):
#   make setup-prerequisites                       # or: ./scripts/setup-prerequisites.sh
#   make setup-prerequisites SETUP_ARGS=-y         # unattended (assume-yes to apt)
#   make setup-prerequisites SETUP_ARGS=--dry-run  # print what would be installed, change nothing
#
# Exit code is non-zero on any hard failure. A final [OK]/[MISSING] summary is
# printed at the end so operators can see at a glance what still needs
# attention (e.g. a reboot or logout to pick up new group memberships).

set -euo pipefail

DRY_RUN=0
APT_YES=""

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -y|--yes)  APT_YES="-y" ;;
    -h|--help)
      sed -n '1,25p' "$0"
      exit 0
      ;;
    *)
      echo "unknown flag: $arg" >&2
      exit 2
      ;;
  esac
done

# ---------------------------------------------------------------- helpers ----

log()  { printf '\n[setup] %s\n' "$*"; }
ok()   { printf '  [OK]      %s\n' "$*"; }
miss() { printf '  [MISSING] %s\n' "$*"; }
info() { printf '  [INFO]    %s\n' "$*"; }

# Track summary
declare -a SUMMARY

run() {
  # Log the command; execute it unless --dry-run
  printf '    $ %s\n' "$*"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    return 0
  fi
  eval "$@"
}

need_root() {
  # Any command that touches /etc, /usr, /var, or apt needs sudo. We never
  # store the sudo password; the user is prompted by sudo directly.
  if [[ "$EUID" -eq 0 ]]; then
    echo ""
  else
    echo "sudo"
  fi
}

SUDO="$(need_root)"

apt_installed() {
  dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q "install ok installed"
}

apt_install() {
  # Install any of the given packages that are not already installed. Empty
  # list is a no-op.
  local pending=()
  for p in "$@"; do
    if apt_installed "$p"; then
      ok "package present: $p"
    else
      miss "package missing: $p"
      pending+=("$p")
    fi
  done
  if [[ "${#pending[@]}" -gt 0 ]]; then
    run "$SUDO apt-get install $APT_YES ${pending[*]}"
  fi
}

apt_update_once() {
  # apt-get update is expensive; run at most once per invocation, and only
  # after we've added a new source list.
  if [[ "${APT_UPDATED:-0}" -eq 1 ]]; then
    return 0
  fi
  run "$SUDO apt-get update"
  APT_UPDATED=1
}

ensure_group() {
  local grp="$1"
  if ! getent group "$grp" >/dev/null 2>&1; then
    miss "group missing: $grp"
    run "$SUDO groupadd -r $grp"
  else
    ok "group exists: $grp"
  fi
  if id -nG "$USER" | tr ' ' '\n' | grep -qx "$grp"; then
    ok "user '$USER' already in group '$grp'"
  else
    miss "user '$USER' not in group '$grp'"
    run "$SUDO usermod -aG $grp $USER"
    SUMMARY+=("Log out and back in for '$grp' group membership to take effect.")
  fi
}

# ------------------------------------------------------------- checks -------

log "Preflight"

# We only officially support Ubuntu 24.04 (noble). The Intel graphics apt repo
# has a per-codename URL so we key off VERSION_CODENAME.
if [[ ! -r /etc/os-release ]]; then
  echo "cannot read /etc/os-release; unsupported OS" >&2
  exit 1
fi
# shellcheck disable=SC1091
. /etc/os-release
info "OS: ${PRETTY_NAME:-unknown}  (ID=${ID:-?}, CODENAME=${VERSION_CODENAME:-?})"

if [[ "${ID:-}" != "ubuntu" || "${VERSION_CODENAME:-}" != "noble" ]]; then
  info "This script is validated on Ubuntu 24.04 (noble)."
  info "It may still work on newer Ubuntu releases if the Intel graphics repo publishes for them."
  SUMMARY+=("Non-noble host: verify intel-graphics repo has packages for '${VERSION_CODENAME:-unknown}'.")
fi

# --------------------------------------------------------- base tools -------

log "Base tools"
apt_install \
  ca-certificates curl gnupg wget \
  git make tar \
  python3 python3-venv python3-pip \
  lsb-release

# ------------------------------------------------------------ Docker --------

log "Docker Engine + Compose v2"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  ok "docker + compose plugin already present ($(docker --version | awk '{print $3}' | tr -d ,))"
else
  miss "docker or compose plugin missing"
  # Docker's official apt repo
  run "$SUDO install -m 0755 -d /etc/apt/keyrings"
  if [[ ! -s /etc/apt/keyrings/docker.gpg ]]; then
    run "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | $SUDO gpg --dearmor -o /etc/apt/keyrings/docker.gpg"
    run "$SUDO chmod a+r /etc/apt/keyrings/docker.gpg"
  fi
  if [[ ! -s /etc/apt/sources.list.d/docker.list ]]; then
    run "echo 'deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable' | $SUDO tee /etc/apt/sources.list.d/docker.list >/dev/null"
    APT_UPDATED=0
  fi
  apt_update_once
  apt_install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

ensure_group docker

# ---------------------------------------------- Intel client GPU stack ------

log "Intel client GPU stack (Level Zero + OpenCL + iHD)"

# Reference: https://dgpu-docs.intel.com/driver/client/overview.html
# Repo key + list are placed under /etc/apt/keyrings and
# /etc/apt/sources.list.d respectively. Idempotent.
if [[ ! -s /usr/share/keyrings/intel-graphics.gpg ]]; then
  miss "intel-graphics apt key missing"
  run "wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | $SUDO gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics.gpg"
else
  ok "intel-graphics apt key present"
fi

INTEL_LIST=/etc/apt/sources.list.d/intel-gpu-${VERSION_CODENAME}.list
if [[ ! -s "$INTEL_LIST" ]]; then
  miss "intel-graphics apt source missing"
  run "echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu ${VERSION_CODENAME} unified' | $SUDO tee $INTEL_LIST >/dev/null"
  APT_UPDATED=0
else
  ok "intel-graphics apt source present"
fi

apt_update_once

apt_install \
  libze1 libze-intel-gpu1 libigc2 libigdgmm12 \
  intel-opencl-icd intel-media-va-driver-non-free \
  clinfo intel-gpu-tools

ensure_group render
ensure_group video

# ----------------------------------------------- device node visibility -----

log "GPU device passthrough (/dev/dri)"

if [[ -d /dev/dri ]]; then
  ok "/dev/dri exists"
  ls -l /dev/dri | sed 's/^/    /'
else
  miss "/dev/dri missing — kernel i915/xe module may not be loaded"
  SUMMARY+=("No /dev/dri on host; iGPU inference will fail. Check dmesg for i915/xe.")
fi

# ------------------------------------------------------------ summary -------

log "Summary"

echo "  OS codename       : ${VERSION_CODENAME:-unknown}"
echo "  Docker            : $(command -v docker >/dev/null 2>&1 && docker --version || echo 'not installed')"
echo "  Compose plugin    : $(docker compose version 2>/dev/null | head -1 || echo 'not installed')"
echo "  Level Zero        : $(dpkg-query -W -f='${Version}' libze1 2>/dev/null || echo 'not installed')"
echo "  Intel iGPU driver : $(dpkg-query -W -f='${Version}' libze-intel-gpu1 2>/dev/null || echo 'not installed')"
echo "  OpenCL runtime    : $(dpkg-query -W -f='${Version}' intel-opencl-icd 2>/dev/null || echo 'not installed')"

if [[ "${#SUMMARY[@]}" -gt 0 ]]; then
  echo
  echo "  Follow-ups:"
  for line in "${SUMMARY[@]}"; do
    echo "    * $line"
  done
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo
  echo "  (dry-run: nothing was changed)"
fi

echo
echo "Next steps:"
echo "  * Log out and back in (or reboot) if you were newly added to a group."
echo "  * Verify GPU access:  ls -l /dev/dri  && clinfo -l"
echo "  * Continue with:      make check-l0 && make backend-venv && make backend-bootstrap"
