#!/bin/bash -e

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
# 4. Process YOLO model (if any)
##############################################################################
mkdir -p src/dlstreamer-pipeline-server/models/public

export MODELS_PATH=/opt/project/src/dlstreamer-pipeline-server/models
chmod +x /home/dlstreamer/dlstreamer/samples/download_public_models.sh
if [ ! -e "src/dlstreamer-pipeline-server/models/public/yolo11s/INT8/yolo11s.xml" ]; then
    for attempt in {1..3}; do
        echo "Attempt $attempt: Running model download and quantization..."
        if /home/dlstreamer/dlstreamer/samples/download_public_models.sh yolo11s coco128; then
            echo "Model download and quantization successful!"
            break
        else
            echo "Download attempt $attempt failed. Retrying..."
            sleep 2
        fi
    done
fi

##############################################################################
# Download and setup videos
##############################################################################
mkdir -p src/dlstreamer-pipeline-server/videos
declare -A video_urls=(
    ["new_video_1.mp4"]="https://github.com/open-edge-platform/edge-ai-resources/raw/0d39322d6c6c578413cdf2a3d48c4e0978531e10/videos/smart_parking_720p_30fps.mp4"
    ["new_video_2.mp4"]="https://github.com/open-edge-platform/edge-ai-resources/raw/0d39322d6c6c578413cdf2a3d48c4e0978531e10/videos/smart_parking_720p_30fps.mp4"
    ["new_video_3.mp4"]="https://github.com/open-edge-platform/edge-ai-resources/raw/0d39322d6c6c578413cdf2a3d48c4e0978531e10/videos/smart_parking_720p_30fps.mp4"
    ["new_video_4.mp4"]="https://github.com/open-edge-platform/edge-ai-resources/raw/0d39322d6c6c578413cdf2a3d48c4e0978531e10/videos/smart_parking_720p_30fps.mp4"
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