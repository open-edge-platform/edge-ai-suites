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
