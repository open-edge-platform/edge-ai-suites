set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

CUSTOM_OPENVINO_INSTALL_DIR=${1:-${CUSTOM_OPENVINO_INSTALL_DIR:-}}
IMAGE_TAG=${2:-tfcc:bevfusion}
DOCKERFILE=${3:-Dockerfile.dockerfile}
BASE=${4:-ubuntu}
BASE_VERSION=${5:-24.04}

if [[ -z "${CUSTOM_OPENVINO_INSTALL_DIR}" ]]; then
    echo "CUSTOM_OPENVINO_INSTALL_DIR is required and must point to a custom OpenVINO install directory containing setupvars.sh." >&2
    echo "Usage: bash docker/build_docker.sh /abs/path/to/custom_openvino/install [IMAGE_TAG] [DOCKERFILE] [BASE] [BASE_VERSION]" >&2
    exit 1
fi

CUSTOM_OPENVINO_INSTALL_DIR=$(realpath "${CUSTOM_OPENVINO_INSTALL_DIR}")

if [[ ! -f "${CUSTOM_OPENVINO_INSTALL_DIR}/setupvars.sh" ]]; then
    echo "CUSTOM_OPENVINO_INSTALL_DIR must point to the install root that contains setupvars.sh: ${CUSTOM_OPENVINO_INSTALL_DIR}" >&2
    exit 1
fi

docker build \
    --network=host \
    --build-arg http_proxy=${http_proxy:-} \
    --build-arg https_proxy=${https_proxy:-} \
    --build-arg BASE="$BASE" \
    --build-arg BASE_VERSION="$BASE_VERSION" \
    --build-arg CUSTOM_OPENVINO_INSTALL_DIR="$CUSTOM_OPENVINO_INSTALL_DIR" \
    --build-context custom_openvino="$CUSTOM_OPENVINO_INSTALL_DIR" \
    -t "$IMAGE_TAG" \
    -f "${SCRIPT_DIR}/$DOCKERFILE" "${SCRIPT_DIR}/.."
