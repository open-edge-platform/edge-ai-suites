#!/bin/bash

docker run --rm --user=root \
  -e http_proxy -e https_proxy -e no_proxy \
  -v "$(dirname "$(readlink -f "$0")"):/opt/project" \
  intel/dlstreamer:2026.2.0-ubuntu24 bash -c "$(cat <<EOF

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
    mkdir -p src/dlstreamer-pipeline-server/models/intel/\${model}/FP16/ && \
    curl -k -L -o "src/dlstreamer-pipeline-server/models/intel/\${model}/FP16/\${model}.xml" "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/\${model}/FP16/\${model}.xml?raw=true" && \
    curl -k -L -o "src/dlstreamer-pipeline-server/models/intel/\${model}/FP16/\${model}.bin" "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/\${model}/FP16/\${model}.bin?raw=true" && \
    echo "Download \$model proc file..." && \
    curl -k -L -o "src/dlstreamer-pipeline-server/models/intel/\${model}/\${model}.json" "https://github.com/dlstreamer/dlstreamer/blob/master/samples/gstreamer/model_proc/intel/\${model}.json?raw=true"

  fi
done

##############################################################################
# Download and convert Ultralytics models to static-shape OpenVINO IRs.
#
# This is what the UI's "model comparison" mode compares the OMZ pedestrian
# detector against. dynamic=False is required: gvadetect's GPU/NPU plugins
# reject a dynamic spatial input shape outright, and on CPU the pipeline
# runs but silently returns no detections. To add another Ultralytics model
# for comparison, add its .pt name (without extension) to ULTRALYTICS_MODELS
# below - the same export call applies to any of them.
##############################################################################
ULTRALYTICS_MODELS=(yolo11s)
ULTRALYTICS_IMGSZ=640
for model in "\${ULTRALYTICS_MODELS[@]}"; do
  ir_dir="src/dlstreamer-pipeline-server/models/\${model}/\${model}_static/FP16"
  if [ ! -e "\${ir_dir}/\${model}.xml" ]; then
    echo "Installing ultralytics and exporting \$model to a static-shape OpenVINO IR..."
    # --trusted-host and the inline requests patch below both skip TLS verification,
    # needed on networks where a corporate proxy intercepts HTTPS with its own CA
    # (pip and ultralytics' GitHub release download otherwise fail with
    # SSLCertVerificationError since that CA is not in this image's trust store).
    if pip install --break-system-packages --quiet --no-cache-dir \
        --trusted-host pypi.org --trusted-host files.pythonhosted.org \
        ultralytics; then
      ( cd /tmp && python3 -c "
import ssl, requests
ssl._create_default_https_context = ssl._create_unverified_context
requests.packages.urllib3.disable_warnings()
_orig_request = requests.Session.request
requests.Session.request = lambda self, *a, **kw: _orig_request(self, *a, **{**kw, 'verify': False})
from ultralytics import YOLO
YOLO('\${model}.pt').export(format='openvino', imgsz=\${ULTRALYTICS_IMGSZ}, dynamic=False, half=True)
" && mkdir -p "/opt/project/\${ir_dir}" \
      && mv "\${model}_openvino_model/\${model}.xml" "\${model}_openvino_model/\${model}.bin" "/opt/project/\${ir_dir}/" \
      && mv "\${model}_openvino_model/metadata.yaml" "/opt/project/\${ir_dir}/metadata.yaml" \
      && rm -rf "\${model}_openvino_model" "\${model}.pt" ) \
      || echo "WARNING: \$model export failed (see above) - place a static-shape IR under \${ir_dir}/ manually if you need it."
    else
      echo "WARNING: could not install ultralytics - place a static-shape IR under \${ir_dir}/ manually if you need it."
    fi
  fi
done

##############################################################################
# Download and setup videos
##############################################################################
mkdir -p src/dlstreamer-pipeline-server/videos
declare -A video_urls=(
    ["VIRAT_S_000101.mp4"]="https://github.com/open-edge-platform/edge-ai-resources/raw/0e0a8e62c1f397412528fb63391632c6b903650b/videos/VIRAT_S_000101.mp4"
    ["VIRAT_S_000102.mp4"]="https://github.com/open-edge-platform/edge-ai-resources/raw/0e0a8e62c1f397412528fb63391632c6b903650b/videos/VIRAT_S_000102.mp4"
    ["VIRAT_S_000103.mp4"]="https://github.com/open-edge-platform/edge-ai-resources/raw/0e0a8e62c1f397412528fb63391632c6b903650b/videos/VIRAT_S_000103.mp4"
    ["VIRAT_S_000104.mp4"]="https://github.com/open-edge-platform/edge-ai-resources/raw/0e0a8e62c1f397412528fb63391632c6b903650b/videos/VIRAT_S_000104.mp4"
)
for video_name in "\${!video_urls[@]}"; do
    if [ ! -f src/dlstreamer-pipeline-server/videos/\${video_name} ]; then
        echo "Download \${video_name}..."
        curl -k -L -o "src/dlstreamer-pipeline-server/videos/\${video_name}" "\${video_urls[\$video_name]}"
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