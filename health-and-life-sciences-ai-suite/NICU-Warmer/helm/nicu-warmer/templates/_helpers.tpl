{{- define "nicu-warmer.name" -}}
nicu-warmer
{{- end }}

{{- define "nicu-warmer.namespace" -}}
{{ .Values.namespace }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "nicu-warmer.labels" -}}
app.kubernetes.io/name: {{ include "nicu-warmer.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
