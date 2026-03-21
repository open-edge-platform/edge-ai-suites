{{- define "lvs.redis.name" -}}
live-video-search
{{- end -}}

{{- define "lvs.redis.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "lvs.redis.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "lvs.redis.labels" -}}
app.kubernetes.io/name: {{ include "lvs.redis.name" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: redis
{{- end -}}

{{- define "lvs.redis.selectorLabels" -}}
app.kubernetes.io/name: {{ include "lvs.redis.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "lvs.redis.vssTag" -}}
{{- default .Values.global.tag .Values.global.vssStackTag -}}
{{- end -}}

{{- define "lvs.redis.smartNvrTag" -}}
{{- default .Values.global.tag .Values.global.smartNvrStackTag -}}
{{- end -}}

{{- define "lvs.redis.image" -}}
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
