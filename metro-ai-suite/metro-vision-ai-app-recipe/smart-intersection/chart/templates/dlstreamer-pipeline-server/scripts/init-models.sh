{{/*
Template for models download init container script
*/}}
{{- define "dlstreamer-pipeline-server.init-models-script" -}}
if [ -f /data/models/.done ]; then
  echo ".done file exists in /data/models"
else
  echo ".done file does NOT exist in /data/models"
  echo "Downloading models from GitHub..."
  apk add --no-cache wget tar
  cd /tmp
  wget -O models.tar.gz {{ .Values.externalUrls.githubRepo }}/archive/refs/tags/{{ .Values.version.modelsRelease }}.tar.gz
  tar -xzf models.tar.gz
  mkdir -p /data/models
  cp -r edge-ai-suites-{{ .Values.version.modelsRelease | replace "v" "" }}/metro-ai-suite/smart-intersection/src/dlstreamer-pipeline-server/models/* /data/models/
  echo "Models downloaded successfully"
  touch /data/models/.done
fi
chown -R 1000:1000 /data
echo "Initializing..."
{{- end -}}
