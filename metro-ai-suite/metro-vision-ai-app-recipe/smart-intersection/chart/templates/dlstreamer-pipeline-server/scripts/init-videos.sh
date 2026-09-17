# This file contains a Helm template that generates the dlstreamer-pipeline-server init-videos script.
# ShellCheck reports syntax errors (SC1054/SC1127) on the Helm template
# directives because they are not valid shell syntax when analyzed directly.
# These findings are expected and cannot be removed without changing the
# Helm template structure. The generated startup script is valid shell code
# and should be ShellChecked after Helm template rendering.
#shellcheck disable=SC1054,SC1127
{{/*
Template for video download init container script
*/}}
{{- define "dlstreamer-pipeline-server.init-videos-script" -}}
if [ -f /data/videos/.done ]; then
    echo ".done file exists in /data/videos"
else
    echo ".done file does NOT exist in /data/videos"
    echo "Downloading videos from GitHub..."
    apk add --no-cache wget
    mkdir -p /data/videos
    VIDEO_URL="{{ .Values.externalUrls.videosRepo }}"
    VIDEOS="1122east_h264.ts 1122west_h264.ts 1122north_h264.ts 1122south_h264.ts"
    for video in $VIDEOS; do
        echo "Downloading $video..."
        wget -O "/data/videos/$video" "$VIDEO_URL/$video"
    done
    echo "Videos downloaded successfully"
    touch /data/videos/.done
fi
chown -R 1000:1000 /data
echo "Initializing..."
{{- end -}}
