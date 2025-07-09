#!/bin/bash -e

docker run --rm --user=root \
  -e http_proxy -e https_proxy -e no_proxy \
  -v "$(dirname "$(readlink -f "$0")"):/opt/project" \
  openvino/ubuntu22_dev:2024.6.0 bash -c "$(cat <<EOF

cd /opt/project
export HOST_IP="${1:-$(hostname -I | cut -f1 -d' ')}"
echo "Configuring application to use \$HOST_IP"

# shellcheck disable=SC1091
. ./update_dashboard.sh \$HOST_IP

##############################################################################
# 4. Process YOLO model (if any)
##############################################################################
mkdir -p src/dlstreamer-pipeline-server/models/public
YOLO_MODELS=(
    yolov10s
)
download_script="\$(
  curl -L -o - 'https://raw.githubusercontent.com/dlstreamer/dlstreamer/refs/tags/v2025.0.1.3/samples/download_public_models.sh'
)"
for model in \${YOLO_MODELS[@]}; do
    if [ ! -e "src/dlstreamer-pipeline-server/models/public/\$model" ]; then
      bash -c "\$(cat <<EOF2
MODELS_PATH=src/dlstreamer-pipeline-server/models
set -- \$model

\$download_script
EOF2
)"
    fi
done

##############################################################################
mkdir -p src/dlstreamer-pipeline-server/models/intel
OMZ_MODELS=(license-plate-recognition-barrier-0007
            vehicle-attributes-recognition-barrier-0039)
for model in "\${OMZ_MODELS[@]}"; do
  if [ ! -e "src/dlstreamer-pipeline-server/models/intel/\$model/\$model.json" ]; then
    mkdir -p "src/dlstreamer-pipeline-server/models/intel/\$model"
    echo "Download \$model..." && \
    omz_downloader --name "\$model" --output_dir src/dlstreamer-pipeline-server/models && \

    echo "Download \$model proc file..." && \
    curl -L -o "src/dlstreamer-pipeline-server/models/intel/\${model}/\${model}.json" "https://raw.githubusercontent.com/dlstreamer/dlstreamer/refs/heads/master/samples/gstreamer/model_proc/intel/license-plate-recognition-barrier-0007.json"
  fi
done

##############################################################################

omz_converter -d src/dlstreamer-pipeline-server/models --name license-plate-recognition-barrier-0007 -o src/dlstreamer-pipeline-server/models/intel/
mv src/dlstreamer-pipeline-server/models/intel/public/license-plate-recognition-barrier-0007/* src/dlstreamer-pipeline-server/models/intel/license-plate-recognition-barrier-0007

##############################################################################

echo "Fix ownership..."
chown -R "$(id -u):$(id -g)" src/dlstreamer-pipeline-server/models src/dlstreamer-pipeline-server/videos 2>/dev/null || true
EOF

)"
