{{- define "lvs.nvrrouter.name" -}}
live-video-search
{{- end -}}

{{- define "lvs.nvrrouter.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "lvs.nvrrouter.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "lvs.nvrrouter.labels" -}}
app.kubernetes.io/name: {{ include "lvs.nvrrouter.name" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: nvr-event-router
{{- end -}}

{{- define "lvs.nvrrouter.selectorLabels" -}}
app.kubernetes.io/name: {{ include "lvs.nvrrouter.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "lvs.nvrrouter.smartNvrTag" -}}
{{- default .Values.global.tag .Values.global.smartNvrStackTag -}}
{{- end -}}

{{- define "lvs.nvrrouter.image" -}}
{{- $registry := .registry -}}
{{- $repository := .repository -}}
{{- $tag := .tag -}}
{{- if $registry -}}
{{ trimSuffix "/" $registry }}/{{ $repository }}:{{ $tag }}
{{- else -}}
intel/{{ $repository }}:{{ $tag }}
{{- end -}}
{{- end -}}
