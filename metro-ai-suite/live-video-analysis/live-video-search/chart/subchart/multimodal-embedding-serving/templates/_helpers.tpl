{{- define "lvs.mmes.name" -}}
live-video-search
{{- end -}}

{{- define "lvs.mmes.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "lvs.mmes.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "lvs.mmes.labels" -}}
app.kubernetes.io/name: {{ include "lvs.mmes.name" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: multimodal-embedding-serving
{{- end -}}

{{- define "lvs.mmes.selectorLabels" -}}
app.kubernetes.io/name: {{ include "lvs.mmes.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "lvs.mmes.vssTag" -}}
{{- default .Values.global.tag .Values.global.vssStackTag -}}
{{- end -}}

{{- define "lvs.mmes.image" -}}
{{- $registry := .registry | default "" -}}
{{- $repository := .repository -}}
{{- $tag := .tag -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" (trimSuffix "/" $registry) $repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}
{{- end -}}
