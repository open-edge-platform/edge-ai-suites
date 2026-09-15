# This file contains a Helm template that generates the dlstreamer-pipeline-server startup script.
# ShellCheck reports syntax errors (SC1054/SC1127) on the Helm template
# directives because they are not valid shell syntax when analyzed directly.
# These findings are expected and cannot be removed without changing the
# Helm template structure. The generated startup script is valid shell code
# and should be ShellChecked after Helm template rendering.
#shellcheck disable=SC1054,SC1127
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
{{- if or .Values.dlstreamerPipelineServer.gpu.enabled .Values.dlstreamerPipelineServer.npu.enabled }}
./run.sh
{{- else if and .Values.trustedCompute.enabled (or .Values.trustedCompute.tc_gpu_enabled .Values.trustedCompute.tc_npu_enabled) }}
i=0
until vainfo 2>/dev/null | grep -q "VA-API version"; do
  i=$((i+1)); [ $i -ge 15 ] && echo "Timed out waiting for GPU VA-API" && exit 1
  echo "Waiting for GPU VA-API..."; sleep 1
done &&
{{- if .Values.trustedCompute.tc_npu_enabled }}
i=0
until [ -e /dev/accel/accel0 ]; do
  i=$((i+1)); [ $i -ge 15 ] && echo "Timed out waiting for NPU device" && exit 1
  echo "Waiting for NPU device..."; sleep 1
done &&
{{- end }}
./run.sh
{{- else }}
runuser -u intelmicroserviceuser ./run.sh
{{- end }}
{{- end -}}
