#!/bin/bash

# Prerequisite setup for the Surgical Instrument (endoscopy) demo.
#
# Verifies/installs the host dependencies needed to run `make up`:
#   - Docker Engine + Compose plugin
#   - membership in the `docker` group
#   - (optional) common developer tools
#
# Proxy is OPTIONAL. Most machines need nothing here. If you are behind a
# corporate proxy, export the standard variables BEFORE running this script:
#
#   export HTTP_PROXY=http://your-proxy:port
#   export HTTPS_PROXY=http://your-proxy:port
#   export NO_PROXY=localhost,127.0.0.1
#   ./setup-prerequisites.sh
#
# Nothing Intel-internal (no hardcoded proxies, certificates, or registry
# credentials) is configured. Images are pulled from public registries.

set -e

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION - optional, read from the environment (empty = not used)
# ═══════════════════════════════════════════════════════════════════════════
HTTP_PROXY="${HTTP_PROXY:-${http_proxy:-}}"
HTTPS_PROXY="${HTTPS_PROXY:-${https_proxy:-}}"
NO_PROXY="${NO_PROXY:-${no_proxy:-localhost,127.0.0.1}}"

# ═══════════════════════════════════════════════════════════════════════════
# PRIVILEGE HANDLING
# When already root, run privileged commands directly (sudo may be absent).
# Otherwise require sudo up front so we fail fast with a clear message rather
# than midway through the install.
# ═══════════════════════════════════════════════════════════════════════════
if [ "$(id -u)" -eq 0 ]; then
    sudo() { "$@"; }
elif ! command -v sudo &> /dev/null; then
    echo "ERROR: root privileges are required but 'sudo' is not installed."
    echo "Re-run this script as root, or install sudo and add your user to sudoers."
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════
# COLORS & FORMATTING
# ═══════════════════════════════════════════════════════════════════════════
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════
log_info()  { echo -e "  ${GREEN}[ OK ] $1${NC}"; }
log_step()  { echo -e "  ${CYAN}[ .. ] $1${NC}"; }
log_warn()  { echo -e "  ${YELLOW}[WARN] $1${NC}"; }
log_error() { echo -e "  ${RED}[FAIL] $1${NC}"; }

log_header() {
    echo ""
    echo -e "${BLUE}==============================================================${NC}"
    echo -e "${BLUE}  ${BOLD}$1${NC}"
    echo -e "${BLUE}==============================================================${NC}"
}

log_section() {
    echo ""
    echo -e "  ${MAGENTA}---- $1 ----${NC}"
}

# ═══════════════════════════════════════════════════════════════════════════
# ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════
handle_error() {
    local exit_code=$?
    local line_number=$1
    if [ $exit_code -ne 0 ]; then
        echo ""
        log_error "Script failed at line $line_number (exit $exit_code)."
        log_error "Command: ${BASH_COMMAND}"
    fi
}
trap 'handle_error $LINENO' ERR

# Run a command quietly; show its output only if it fails.
exec_cmd() {
    local output_file
    output_file=$(mktemp)
    if ! "$@" > "$output_file" 2>&1; then
        echo ""
        log_error "Command failed: $*"
        echo -e "${YELLOW}----------------------------- output --------------------------${NC}"
        cat "$output_file"
        echo -e "${YELLOW}---------------------------------------------------------------${NC}"
        rm -f "$output_file"
        return 1
    fi
    rm -f "$output_file"
    return 0
}

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
log_header "Surgical Instrument - Prerequisite Setup"

# Detect OS.
if [ -f /etc/os-release ]; then
    . /etc/os-release
else
    log_error "/etc/os-release not found. Cannot determine OS."
    exit 1
fi
log_info "Detected OS: ${NAME:-unknown} (${VERSION:-?})"

if [[ "${ID:-}" != "ubuntu" && ! "${NAME:-}" =~ [Uu]buntu ]]; then
    log_warn "This installer is tested on Ubuntu. On other distros it will only"
    log_warn "verify Docker and skip apt-based installs."
fi

# ───────────────────────────────────────────────────────────────────────────
# Optional proxy configuration (only if the user provided one)
# ───────────────────────────────────────────────────────────────────────────
log_section "Proxy"
if [ -n "$HTTP_PROXY" ] || [ -n "$HTTPS_PROXY" ]; then
    log_step "Applying proxy for this session and Docker daemon..."
    export http_proxy="$HTTP_PROXY"  https_proxy="$HTTPS_PROXY"  no_proxy="$NO_PROXY"
    export HTTP_PROXY HTTPS_PROXY NO_PROXY

    # Docker daemon proxy (systemd drop-in).
    if command -v systemctl &> /dev/null; then
        sudo mkdir -p /etc/systemd/system/docker.service.d
        sudo tee /etc/systemd/system/docker.service.d/http-proxy.conf > /dev/null <<EOF
[Service]
Environment="HTTP_PROXY=$HTTP_PROXY"
Environment="HTTPS_PROXY=$HTTPS_PROXY"
Environment="NO_PROXY=$NO_PROXY"
EOF
        log_info "Docker daemon proxy configured (restart Docker to apply)."
    fi
else
    log_info "No proxy set - direct internet access assumed (typical setup)."
    log_info "Behind a corporate proxy? Re-run with HTTP_PROXY / HTTPS_PROXY exported."
fi

# ───────────────────────────────────────────────────────────────────────────
# Docker Engine + Compose
# ───────────────────────────────────────────────────────────────────────────
log_section "Docker"
if command -v docker &> /dev/null; then
    log_info "Docker is installed: $(docker --version)"
elif [[ "${ID:-}" == "ubuntu" || "${NAME:-}" =~ [Uu]buntu ]]; then
    log_step "Docker not found - installing Docker Engine + Compose..."
    exec_cmd sudo apt-get update -qq
    exec_cmd sudo apt-get install -y -qq apt-transport-https ca-certificates curl gnupg lsb-release
    sudo install -m 0755 -d /etc/apt/keyrings
    exec_cmd bash -c "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg"
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    exec_cmd bash -c "echo \"deb [arch=\$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \$(. /etc/os-release && echo \"\$VERSION_CODENAME\") stable\" | sudo tee /etc/apt/sources.list.d/docker.list"
    exec_cmd sudo apt-get update -qq
    exec_cmd sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    log_info "Docker installed: $(docker --version)"
else
    log_error "Docker is not installed and auto-install is only supported on Ubuntu."
    log_error "Please install Docker manually: https://docs.docker.com/engine/install/"
    exit 1
fi

# Compose plugin check.
if docker compose version &> /dev/null; then
    log_info "Docker Compose available: $(docker compose version --short 2>/dev/null)"
else
    log_warn "Docker Compose plugin not found - 'make up' needs it."
    log_warn "Install with: sudo apt-get install -y docker-compose-plugin"
fi

# docker group membership (so the user can run docker without sudo).
CURRENT_USER=$(whoami)
if groups "$CURRENT_USER" | grep -qw docker; then
    log_info "User '$CURRENT_USER' is in the docker group."
else
    log_step "Adding '$CURRENT_USER' to the docker group..."
    sudo usermod -aG docker "$CURRENT_USER"
    log_warn "Log out and back in (or run 'newgrp docker') for this to take effect."
fi

# ───────────────────────────────────────────────────────────────────────────
# Required host tools for `make up` (make + git to run/clone; curl for helpers)
# ───────────────────────────────────────────────────────────────────────────
if [[ "${ID:-}" == "ubuntu" || "${NAME:-}" =~ [Uu]buntu ]]; then
    log_section "Required tools (make, git, curl)"
    log_step "Ensuring make, git, and curl are installed..."
    exec_cmd sudo apt-get update -qq
    exec_cmd sudo apt-get install -y -qq make git curl
    log_info "make: $(make --version | head -1)"
    log_info "git:  $(git --version)"
else
    for t in make git curl; do
        if command -v "$t" &> /dev/null; then
            log_info "$t is installed."
        else
            log_warn "$t not found - install it before running 'make up'."
        fi
    done
fi

# ───────────────────────────────────────────────────────────────────────────
# Optional developer tools
# ───────────────────────────────────────────────────────────────────────────
if [[ "${ID:-}" == "ubuntu" || "${NAME:-}" =~ [Uu]buntu ]]; then
    log_section "Optional developer tools"
    INSTALL_TOOLS=""
    if [ -t 0 ]; then
        read -r -p "  Install extra tools (python3, build-essential)? (y/N): " INSTALL_TOOLS || true
    else
        log_info "Non-interactive run - skipping optional tools prompt."
    fi
    if [[ "$INSTALL_TOOLS" =~ ^[Yy]$ ]]; then
        log_step "Installing python3 and build-essential..."
        exec_cmd sudo apt-get update -qq
        exec_cmd sudo apt-get install -y -qq build-essential python3 python3-venv python3-pip
        log_info "Optional tools installed."
    else
        log_info "Skipped optional developer tools (not needed to run the app)."
    fi
fi

# ───────────────────────────────────────────────────────────────────────────
# Done
# ───────────────────────────────────────────────────────────────────────────
log_header "Setup complete"
echo -e "  Next steps:"
echo -e "    ${CYAN}cd ..${NC}                 # surgical-instrument project root"
echo -e "    ${CYAN}make up${NC}               # start the demo (see docs/get-started.md)"
echo ""
if ! groups "$CURRENT_USER" | grep -qw docker; then
    log_warn "Remember to re-login so your docker group membership applies."
fi
