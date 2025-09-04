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
    VIDEOS="1122east.ts 1122west.ts 1122north.ts 1122south.ts"
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
