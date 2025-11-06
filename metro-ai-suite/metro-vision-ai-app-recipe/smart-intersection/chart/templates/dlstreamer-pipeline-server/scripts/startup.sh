{{/*
Template for main container startup script
*/}}
{{- define "dlstreamer-pipeline-server.startup-script" -}}
mkdir -p /run/secrets/certs &&
cp /home/pipeline-server/certs/root-cert /run/secrets/certs/scenescape-ca.pem &&
cp /tmp/pipeline/config.json . &&
mkdir -p /home/pipeline-server/user_scripts/gvapython/sscape &&
cp /tmp/udf/config.json /home/pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py &&
chmod a+rwx /home/pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py &&
chown -R intelmicroserviceuser:intelmicroserviceuser /home/pipeline-server/models &&
chown -R intelmicroserviceuser:intelmicroserviceuser /home/pipeline-server/videos &&
echo "$SMART_INTERSECTION_BROKER_SERVICE_HOST    $MQTT_HOST" >> /etc/hosts &&
{{- if .Values.dlstreamerPipelineServer.gpuWorkload }}
./run.sh
{{- else }}
runuser -u intelmicroserviceuser ./run.sh
{{- end }}
{{- end -}}
