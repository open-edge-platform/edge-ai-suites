{{- define "lvs.postgres.name" -}}
live-video-search
{{- end -}}

{{- define "lvs.postgres.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "lvs.postgres.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "lvs.postgres.labels" -}}
app.kubernetes.io/name: {{ include "lvs.postgres.name" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: postgres-service
{{- end -}}

{{- define "lvs.postgres.selectorLabels" -}}
app.kubernetes.io/name: {{ include "lvs.postgres.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "lvs.postgres.vssTag" -}}
{{- default .Values.global.tag .Values.global.vssStackTag -}}
{{- end -}}

{{- define "lvs.postgres.smartNvrTag" -}}
{{- default .Values.global.tag .Values.global.smartNvrStackTag -}}
{{- end -}}

{{- define "lvs.postgres.image" -}}
{{- $registry := .registry | default "" -}}
{{- $repository := .repository -}}
{{- $tag := .tag -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" (trimSuffix "/" $registry) $repository $tag -}}
{{- else -}}
{{- if contains "/" $repository -}}
{{- printf "docker.io/%s:%s" $repository $tag -}}
{{- else -}}
{{- printf "docker.io/intel/%s:%s" $repository $tag -}}
{{- end -}}
{{- end -}}
{{- end -}}
