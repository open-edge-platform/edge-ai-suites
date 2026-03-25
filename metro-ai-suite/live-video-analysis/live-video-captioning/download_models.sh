#!/usr/bin/env bash
set -euo pipefail

# Download and export OpenVINO GenAI models into ov_models using optimum-cli.
# Models and commands are based on the gvagenai sample (MiniCPM-V 2.6, Phi-4-multimodal-instruct, Gemma 3, InternVL2-2B, SmolVLM2-256M)
# and the export dependencies listed in the OpenVINO GenAI export-requirements.txt.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
MODELS_DIR="${SCRIPT_DIR}/ov_models"
REQUIREMENTS_URL="https://raw.githubusercontent.com/openvinotoolkit/openvino.genai/refs/tags/2025.4.1.0/samples/export-requirements.txt"
DEFAULT_MODEL="internvl2_1B"
VALID_WEIGHT_FORMATS=("fp16" "int8" "int4")

usage() {
  cat <<EOF
Usage: $(basename "$0") [MODEL_KEY] [--weight-format FORMAT]

MODEL_KEY options:
  gemma3    -> google/gemma-3-4b-it
  internvl2_1B -> OpenGVLab/InternVL2-1B
  internvl2_2B -> OpenGVLab/InternVL2-2B
  <hf_id>   -> any other Hugging Face repo id (warned)

Weight format options (quantization):
  fp16  -> FP16 precision (default, no quantization)
  int8  -> 8-bit weight quantization via NNCF
  int4  -> 4-bit weight quantization via NNCF (best compression)

Examples:
  $(basename "$0") internvl2_1B
  $(basename "$0") internvl2_1B --weight-format int4
  $(basename "$0") Qwen/Qwen2.5-VL-3B-Instruct --weight-format int8
EOF
}

MODEL_KEY=""
WEIGHT_FORMAT=""
MODEL_ID=""
OUTPUT_NAME=""
EXTRA_ARGS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --weight-format)
      if [[ -z "${2:-}" ]]; then
        echo "Error: --weight-format requires a value (fp16, int8, int4)." >&2
        exit 1
      fi
      WEIGHT_FORMAT="$2"
      shift 2
      ;;
    *)
      if [[ -z "$MODEL_KEY" ]]; then
        MODEL_KEY="$1"
      else
        echo "Error: unexpected argument '$1'." >&2
        usage
        exit 1
      fi
      shift
      ;;
  esac
done

MODEL_KEY="${MODEL_KEY:-$DEFAULT_MODEL}"

# Validate weight format if provided
if [[ -n "$WEIGHT_FORMAT" ]]; then
  valid=false
  for fmt in "${VALID_WEIGHT_FORMATS[@]}"; do
    if [[ "$WEIGHT_FORMAT" == "$fmt" ]]; then
      valid=true
      break
    fi
  done
  if [[ "$valid" == false ]]; then
    echo "Error: invalid weight format '$WEIGHT_FORMAT'. Must be one of: ${VALID_WEIGHT_FORMATS[*]}" >&2
    exit 1
  fi
fi

case "$MODEL_KEY" in
  gemma3|gemma-3|gemma-3-4b-it)
    MODEL_ID="google/gemma-3-4b-it"
    OUTPUT_NAME="Gemma3"
    ;;
  internvl2_2B|internvl2-2b|OpenGVLab/InternVL2-2B|internvl2_2b)
    MODEL_ID="OpenGVLab/InternVL2-2B"
    OUTPUT_NAME="InternVL2-2B"
    ;;
  internvl2_1B|internvl2-1b|OpenGVLab/InternVL2-1B|internvl2_1b)
    MODEL_ID="OpenGVLab/InternVL2-1B"
    OUTPUT_NAME="InternVL2-1B"
    ;;
  *)
    MODEL_ID="$MODEL_KEY"
    OUTPUT_NAME="${MODEL_KEY##*/}"
    echo "Warning: proceeding with custom model id '$MODEL_KEY' (not in supported list)." >&2
    ;;
esac

# Append weight format suffix to output name and add to export args
if [[ -n "$WEIGHT_FORMAT" ]]; then
  OUTPUT_NAME="${OUTPUT_NAME}-${WEIGHT_FORMAT}-ov"
  EXTRA_ARGS+=("--weight-format" "$WEIGHT_FORMAT")
  echo "Quantization: --weight-format $WEIGHT_FORMAT"
fi

if [[ -n "${HF_TOKEN:-}" && -z "${HUGGINGFACEHUB_API_TOKEN:-}" ]]; then
  export HUGGINGFACEHUB_API_TOKEN="$HF_TOKEN"
fi

if [[ -z "${HF_TOKEN:-}" && -z "${HUGGINGFACEHUB_API_TOKEN:-}" ]]; then
  echo "Warning: if the model is gated, set HF_TOKEN or HUGGINGFACEHUB_API_TOKEN to avoid download failures." >&2
fi

mkdir -p "$MODELS_DIR"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090,SC1091
source "$VENV_DIR/bin/activate"
python3 -m pip install --upgrade pip
python3 -m pip install -r "$REQUIREMENTS_URL"

export HF_HUB_ENABLE_HF_TRANSFER="${HF_HUB_ENABLE_HF_TRANSFER:-1}"

OUTPUT_PATH="${MODELS_DIR}/${OUTPUT_NAME}"
if [ -d "$OUTPUT_PATH" ]; then
  echo "Model directory already exists: $OUTPUT_PATH" >&2
  echo "Remove it first if you want to re-export." >&2
  exit 1
fi

echo "Exporting $MODEL_ID to $OUTPUT_PATH"
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  optimum-cli export openvino --model "$MODEL_ID" "${EXTRA_ARGS[@]}" "$OUTPUT_PATH" --trust-remote-code
else
  optimum-cli export openvino --model "$MODEL_ID" "$OUTPUT_PATH" --trust-remote-code
fi

echo "Model saved to $OUTPUT_PATH"
