{{- define "lvs.videosearch.name" -}}
live-video-search
{{- end -}}

{{- define "lvs.videosearch.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "lvs.videosearch.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "lvs.videosearch.labels" -}}
app.kubernetes.io/name: {{ include "lvs.videosearch.name" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: video-search
{{- end -}}

{{- define "lvs.videosearch.selectorLabels" -}}
app.kubernetes.io/name: {{ include "lvs.videosearch.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "lvs.videosearch.vssTag" -}}
{{- default .Values.global.tag .Values.global.vssStackTag -}}
{{- end -}}

{{- define "lvs.videosearch.image" -}}
{{- $registry := .registry -}}
{{- $repository := .repository -}}
{{- $tag := .tag -}}
{{- if $registry -}}
{{ trimSuffix "/" $registry }}/{{ $repository }}:{{ $tag }}
{{- else -}}
intel/{{ $repository }}:{{ $tag }}
{{- end -}}
{{- end -}}
