#!/usr/bin/env bash

set -o pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR" || exit 1

DATASET_PATH="${DATASET_PATH:-ai_inference/test/demo/kitti360}"
SERVICE_SCRIPT="${SERVICE_SCRIPT:-./run_service_bare_log.sh}"

# Configurable parameters (can be overridden via environment variables)
RUNS=${RUNS:-1}
SERVICE_STARTUP_SLEEP_SECONDS=${SERVICE_STARTUP_SLEEP_SECONDS:-8}
SERVICE_SHUTDOWN_SLEEP_SECONDS=${SERVICE_SHUTDOWN_SLEEP_SECONDS:-3}
TIMEOUT_SECONDS=${TIMEOUT_SECONDS:-30000}
LOG_DIR=${LOG_DIR:-$PROJECT_DIR/test/autotest_logs}

die() {
    echo "[ERROR] $*" >&2
    exit 1
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

require_cmd timeout
require_cmd awk
require_cmd tee

# Simple colored output (enabled only on TTY unless forced)
COLOR_MODE=${COLOR_MODE:-auto} # auto|always|never
USE_COLOR=0
if [[ "$COLOR_MODE" == "always" ]]; then
    USE_COLOR=1
elif [[ "$COLOR_MODE" == "auto" ]]; then
    if [[ -t 1 && "${TERM:-}" != "dumb" && -z "${NO_COLOR:-}" ]]; then
        USE_COLOR=1
    fi
fi

if [[ $USE_COLOR -eq 1 ]]; then
    C_GREEN=$'\033[32m'
    C_RED=$'\033[31m'
    C_YELLOW=$'\033[33m'
    C_RESET=$'\033[0m'
else
    C_GREEN=""
    C_RED=""
    C_YELLOW=""
    C_RESET=""
fi

print_case_status() {
    local scenario="$1"
    local run="$2"
    local exit_code="$3"

    if [[ "$exit_code" -eq 0 ]]; then
        echo "${C_GREEN}[CASE] ${scenario} Run ${run}: PASS${C_RESET}"
    elif [[ "$exit_code" -eq 124 ]]; then
        echo "${C_YELLOW}[CASE] ${scenario} Run ${run}: TIMEOUT${C_RESET}"
    else
        echo "${C_RED}[CASE] ${scenario} Run ${run}: FAIL (exit=${exit_code})${C_RESET}"
    fi
}

SUDO_CMD=""
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO_CMD="sudo -E"
    else
        die "Not running as root and sudo is not installed. Run as root or install sudo."
    fi
fi

if [[ -n "$SUDO_CMD" ]]; then
    if ! sudo -n true >/dev/null 2>&1; then
        echo "[WARN] sudo may prompt for a password during execution. If running non-interactively, configure passwordless sudo for required commands." >&2
    fi
fi

mkdir -p "$LOG_DIR" || die "Failed to create LOG_DIR: $LOG_DIR"

[[ -f "$SERVICE_SCRIPT" ]] || die "Service script not found: $SERVICE_SCRIPT"

# ==============================
# Define the commands to execute
# Each line is a complete runnable command (as you would type in a terminal)
# ==============================
declare -a COMMANDS=(
    "./build/bin/testGRPCCPlusLPipeline 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localFusionPipeline.json 1 1 $DATASET_PATH multisensor"
    "./build/bin/testGRPCCPlusLPipeline 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localFusionPipeline.json 2 1 $DATASET_PATH multisensor"
    "./build/bin/testGRPCCPlusLPipeline 127.0.0.1 50052 ai_inference/test/configs/kitti/2C1L/localFusionPipeline.json 4 1 $DATASET_PATH multisensor"
    "./build/bin/testGRPCCPlusLPipeline 127.0.0.1 50052 ai_inference/test/configs/kitti/6C1L/localFusionPipeline.json 2 1 $DATASET_PATH multisensor"
)

# Scenario names (used for CSV labeling)
declare -a SCENARIO_NAMES=("2C1L" "4C2L" "8C4L" "12C2L")

if [[ ${#COMMANDS[@]} -ne ${#SCENARIO_NAMES[@]} ]]; then
    die "COMMANDS and SCENARIO_NAMES length mismatch: ${#COMMANDS[@]} vs ${#SCENARIO_NAMES[@]}"
fi

# Validate required binaries exist before running any benchmarks.
for cmd in "${COMMANDS[@]}"; do
    # First token is the executable path.
    set -- $cmd
    exe="$1"
    if [[ ! -x "$exe" ]]; then
        die "Required test binary not found or not executable: $exe. Build first so build outputs exist under ./build/bin/."
    fi
done

CSV_FILE="$LOG_DIR/benchmark_results_$(date +%Y%m%d_%H%M%S).csv"

# ==============================
# Initialize CSV file (fixed column order)
# ==============================
echo "scenario,run,fps,inference_avg_latency,video_pipeline_avg_latency,average_latency,lidar_avg_latency,cpuUtilizationVal,gpuAllUtilizationVal" > "$CSV_FILE"

start_service() {
    echo "[INFO] Starting service..."
    $SUDO_CMD bash "$SERVICE_SCRIPT" &
    SERVICE_LAUNCH_PID=$!
    sleep "$SERVICE_STARTUP_SLEEP_SECONDS"
}

stop_service() {
    echo "[INFO] Killing Hce processes..."
    $SUDO_CMD pkill Hce >/dev/null 2>&1 || true
    if [[ -n "${SERVICE_LAUNCH_PID:-}" ]]; then
        $SUDO_CMD kill "$SERVICE_LAUNCH_PID" >/dev/null 2>&1 || true
        SERVICE_LAUNCH_PID=""
    fi
    sleep "$SERVICE_SHUTDOWN_SLEEP_SECONDS"
}

cleanup() {
    stop_service
}

trap cleanup EXIT INT TERM

for idx in "${!COMMANDS[@]}"; do
    if [[ -n "$SUDO_CMD" ]]; then
        FULL_CMD="$SUDO_CMD ${COMMANDS[$idx]}"
    else
        FULL_CMD="${COMMANDS[$idx]}"
    fi
    SCENARIO="${SCENARIO_NAMES[$idx]}"

    echo "========================================"
    echo "[START] Scenario: $SCENARIO"
    echo "Command: $FULL_CMD"
    echo "========================================"

    for ((run=1; run<=RUNS; run++)); do
        echo "[RUN] $SCENARIO - Run $run/$RUNS"

        start_service

        LOG_FILE="$LOG_DIR/log_${SCENARIO}_run${run}.log"

        timeout "$TIMEOUT_SECONDS" bash -c "$FULL_CMD" 2>&1 | tee "$LOG_FILE"
        CMD_EXIT=${PIPESTATUS[0]}

        FPS=$(awk '/^fps:[[:space:]]*/ {val=$2} END{print val}' "$LOG_FILE")
        FPS=${FPS:-""}
        AVG_LATENCY=$(awk '/^average latency/ {val=$3} END{print val}' "$LOG_FILE")
        AVG_LATENCY=${AVG_LATENCY:-""}
        VIDEO_LATENCY=$(awk '/^video pipeline average latency/ {val=$5} END{print val}' "$LOG_FILE")
        VIDEO_LATENCY=${VIDEO_LATENCY:-""}
        INFERENCE_LATENCY=$(awk '/^inference average latency/ {val=$4} END{print val}' "$LOG_FILE")
        INFERENCE_LATENCY=${INFERENCE_LATENCY:-""}
        LIDAR_LATENCY=$(awk '/^lidar average latency/ {val=$4} END{print val}' "$LOG_FILE")
        LIDAR_LATENCY=${LIDAR_LATENCY:-""}

        CPU_UTIL=$(awk -F'cpuUtilizationVal:' '/cpuUtilizationVal:/ {val=$2} END{gsub(/^[[:space:]]+/,"",val); sub(/[^0-9].*$/,"",val); print val}' "$LOG_FILE")
        CPU_UTIL=${CPU_UTIL:-""}
        GPU_UTIL=$(awk -F'gpuAllUtilizationVal:' '/gpuAllUtilizationVal:/ {val=$2} END{gsub(/^[[:space:]]+/,"",val); sub(/[^0-9-].*$/,"",val); print val}' "$LOG_FILE")
        GPU_UTIL=${GPU_UTIL:-""}

        echo "$SCENARIO,$run,$FPS,$INFERENCE_LATENCY,$VIDEO_LATENCY,$AVG_LATENCY,$LIDAR_LATENCY,$CPU_UTIL,$GPU_UTIL" >> "$CSV_FILE"
        echo "[RESULT] $SCENARIO Run $run -> exit: $CMD_EXIT, fps: $FPS, avg_lat: $AVG_LATENCY, cpu: $CPU_UTIL%, gpu: $GPU_UTIL%"
        print_case_status "$SCENARIO" "$run" "$CMD_EXIT"

        stop_service
        echo "----------------------------------------"
    done
done

echo "[SUCCESS] All benchmarks completed. Results saved to: $CSV_FILE"
