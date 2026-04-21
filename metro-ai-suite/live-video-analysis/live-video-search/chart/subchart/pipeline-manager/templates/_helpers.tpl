{{- define "lvs.pipeline.name" -}}
live-video-search
{{- end -}}

{{- define "lvs.pipeline.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "lvs.pipeline.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "lvs.pipeline.labels" -}}
app.kubernetes.io/name: {{ include "lvs.pipeline.name" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: pipeline-manager
{{- end -}}

{{- define "lvs.pipeline.selectorLabels" -}}
app.kubernetes.io/name: {{ include "lvs.pipeline.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "lvs.pipeline.vssTag" -}}
{{- default .Values.global.tag .Values.global.vssStackTag -}}
{{- end -}}

{{- define "lvs.pipeline.image" -}}
{{- $registry := .registry -}}
{{- $repository := .repository -}}
{{- $tag := .tag -}}
{{- if $registry -}}
{{ trimSuffix "/" $registry }}/{{ $repository }}:{{ $tag }}
{{- else -}}
intel/{{ $repository }}:{{ $tag }}
{{- end -}}
{{- end -}}
