{{- define "lvs.vssui.name" -}}
live-video-search
{{- end -}}

{{- define "lvs.vssui.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "lvs.vssui.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "lvs.vssui.labels" -}}
app.kubernetes.io/name: {{ include "lvs.vssui.name" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: vss-ui
{{- end -}}

{{- define "lvs.vssui.selectorLabels" -}}
app.kubernetes.io/name: {{ include "lvs.vssui.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "lvs.vssui.vssTag" -}}
{{- default .Values.global.tag .Values.global.vssStackTag -}}
{{- end -}}

{{- define "lvs.vssui.image" -}}
{{- $registry := .registry -}}
{{- $repository := .repository -}}
{{- $tag := .tag -}}
{{- if $registry -}}
{{ trimSuffix "/" $registry }}/{{ $repository }}:{{ $tag }}
{{- else -}}
intel/{{ $repository }}:{{ $tag }}
{{- end -}}
{{- end -}}
