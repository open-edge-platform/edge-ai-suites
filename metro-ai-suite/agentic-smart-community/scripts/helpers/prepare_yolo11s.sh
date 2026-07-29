PREFILTER_MODEL=${PREFILTER_MODEL:-${HOME}/models/openvino/yolo11s/FP16/yolo11s.xml}
PREFILTER_BIN="${PREFILTER_MODEL%.xml}.bin"

if ! declare -F info >/dev/null; then
    info() { printf '[info] %s\n' "$*"; }
    step() { printf '[step] %s\n' "$*"; }
    ok() { printf '[ ok ] %s\n' "$*"; }
    err() { printf '[err ] %s\n' "$*" >&2; }
fi

if ! declare -F run >/dev/null; then
    run() { "$@"; }
fi

echo "Build YOLO11s OpenVINO IR for NPU (1280x704 FP16 static)"

if [[ -f "$PREFILTER_MODEL" && -f "$PREFILTER_BIN" ]]; then
    info "Already present: $PREFILTER_MODEL"
    return 0 2>/dev/null || exit 0
fi

work_dir="/tmp/openvino/_work"
venv_dir="$work_dir/convert_venv"
weights="$work_dir/yolo11s.pt"
helper_dir=
helper_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
converter="$helper_dir/convert_yolo_ov.py"

if [[ ! -f "$converter" ]]; then
    err "Converter script missing: $converter"
    exit 2
fi

mkdir -p "$work_dir"

if [[ ! -d "$venv_dir" ]]; then
    step "Creating throwaway venv at $venv_dir"
    run python3 -m venv "$venv_dir" || { err "venv create failed"; exit 2; }
fi

run "$venv_dir/bin/python" -m pip install --quiet --upgrade pip || {
    err "pip upgrade failed"
    exit 2
}
run "$venv_dir/bin/pip" install --quiet ultralytics openvino || {
    err "pip install ultralytics openvino failed"
    exit 2
}

if [[ ! -f "$weights" ]]; then
    step "Downloading yolo11s.pt → $weights"
    weights_tmp="${weights}.download"
    rm -f "$weights_tmp"
    run wget --https-only --quiet \
        https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s.pt \
        -O "$weights_tmp" && mv "$weights_tmp" "$weights" || {
            rm -f "$weights_tmp"
            err "Downloading yolo11s.pt failed"
            exit 2
        }
fi

step "Converting to FP16 static-shape OpenVINO IR (1280x704)"
run "$venv_dir/bin/python" "$converter" \
    --weights "$weights" \
    --precision FP16 \
    --xml-path "$PREFILTER_MODEL" \
    --bin-path "$PREFILTER_BIN" \
    --dynamic False \
    --imgsz 704 1280 \
    || {
    err "yolo conversion failed"
    exit 2
    }

if [[ ! -s "$PREFILTER_MODEL" || ! -s "$PREFILTER_BIN" ]]; then
    err "Conversion finished but the IR pair is incomplete: $PREFILTER_MODEL"
    exit 2
fi

step "Cleaning up throwaway venv"
run rm -rf "$venv_dir"

ok "Done — IR ready at $PREFILTER_MODEL"