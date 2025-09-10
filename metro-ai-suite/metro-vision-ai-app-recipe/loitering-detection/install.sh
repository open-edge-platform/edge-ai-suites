#!/bin/bash

docker run --rm --user=root \
  -e http_proxy -e https_proxy -e no_proxy \
  -v "$(dirname "$(readlink -f "$0")"):/opt/project" \
  intel/dlstreamer:2025.1.2-ubuntu24 bash -c "$(cat <<EOF

cd /opt/project
export HOST_IP="${1:-$(hostname -I | cut -f1 -d' ')}"
echo "Configuring application to use \$HOST_IP"

# shellcheck disable=SC1091
. ./update_dashboard.sh \$HOST_IP

##############################################################################
# Download OMZ models
##############################################################################
mkdir -p src/dlstreamer-pipeline-server/models/intel
OMZ_MODELS=(pedestrian-and-vehicle-detector-adas-0001)
for model in "\${OMZ_MODELS[@]}"; do
  if [ ! -e "src/dlstreamer-pipeline-server/models/intel/\$model/\$model.json" ]; then
    echo "Download \$model..." && \
    mkdir -p src/dlstreamer-pipeline-server/models/intel/\${model}/FP32/ && \
    curl -L -o "src/dlstreamer-pipeline-server/models/intel/\${model}/FP32/\${model}.xml" "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/\${model}/FP32/\${model}.xml?raw=true" && \
    curl -L -o "src/dlstreamer-pipeline-server/models/intel/\${model}/FP32/\${model}.bin" "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/\${model}/FP32/\${model}.bin?raw=true" && \
    echo "Download \$model proc file..." && \
    curl -L -o "src/dlstreamer-pipeline-server/models/intel/\${model}/\${model}.json" "https://github.com/dlstreamer/dlstreamer/blob/master/samples/gstreamer/model_proc/intel/\${model}.json?raw=true"

  fi
done

##############################################################################
# Download and setup videos
##############################################################################
mkdir -p src/dlstreamer-pipeline-server/videos
declare -A video_urls=(
    ["VIRAT_S_000101.mp4"]="https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/VIRAT_S_000101.mp4"
    ["VIRAT_S_000102.mp4"]="https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/VIRAT_S_000102.mp4"
    ["VIRAT_S_000103.mp4"]="https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/VIRAT_S_000103.mp4"
    ["VIRAT_S_000104.mp4"]="https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/VIRAT_S_000104.mp4"
)
for video_name in "\${!video_urls[@]}"; do
    if [ ! -f src/dlstreamer-pipeline-server/videos/\${video_name} ]; then
        echo "Download \${video_name}..."
        curl -L -o "src/dlstreamer-pipeline-server/videos/\${video_name}" "\${video_urls[\$video_name]}"
    fi
done

echo "Fix ownership..."
chown -R "$(id -u):$(id -g)" src/dlstreamer-pipeline-server/models src/dlstreamer-pipeline-server/videos 2>/dev/null || true


mkdir -p src/nginx/ssl
cd src/nginx/ssl
if [ ! -f server.key ] || [ ! -f server.crt ]; then
    echo "Generate self-signed certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout server.key -out server.crt -subj "/C=US/ST=CA/L=San Francisco/O=Intel/OU=Edge AI/CN=localhost"
    chown -R "$(id -u):$(id -g)" server.key server.crt 2>/dev/null || true

fi

EOF

)"
