{{/*
Template for PostgreSQL server init script
*/}}
{{- define "pgserver.init-script" -}}
if [ -f /data/smart-intersection-ri.tar.bz2 ]; then
  echo "File exists: /data/smart-intersection-ri.tar.bz2"
else
  echo "File does NOT exist: /data/smart-intersection-ri.tar.bz2"
  echo "Downloading file from GitHub..."
  apk add --no-cache wget
  wget -O /data/smart-intersection-ri.tar.bz2 "{{ .Values.externalUrls.githubRepo }}/raw/refs/tags/{{ .Values.version.release }}/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/src/webserver/smart-intersection-ri.tar.bz2"
  if [ $? -eq 0 ]; then
    echo "File downloaded successfully to /data/smart-intersection-ri.tar.bz2"
  else
    echo "Failed to download file"
    exit 1
  fi
fi
{{- end -}}
