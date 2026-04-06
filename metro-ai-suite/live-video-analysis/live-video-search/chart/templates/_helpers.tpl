{{- define "lvs.root.validateRequiredString" -}}
{{- $path := index . 0 -}}
{{- $value := index . 1 -}}
{{- if eq (trim (default "" $value)) "" -}}
{{- fail (printf "%s must be set (use user_values_override.yaml or override profiles)" $path) -}}
{{- end -}}
{{- end -}}

{{- define "lvs.root.validate" -}}
{{- include "lvs.root.validateRequiredString" (list "global.env.embeddingModelName" .Values.global.env.embeddingModelName) -}}
{{- include "lvs.root.validateRequiredString" (list "global.credentials.minioRootUser" .Values.global.credentials.minioRootUser) -}}
{{- include "lvs.root.validateRequiredString" (list "global.credentials.minioRootPassword" .Values.global.credentials.minioRootPassword) -}}
{{- include "lvs.root.validateRequiredString" (list "global.credentials.postgresUser" .Values.global.credentials.postgresUser) -}}
{{- include "lvs.root.validateRequiredString" (list "global.credentials.postgresPassword" .Values.global.credentials.postgresPassword) -}}
{{- include "lvs.root.validateRequiredString" (list "global.credentials.mqttUser" .Values.global.credentials.mqttUser) -}}
{{- include "lvs.root.validateRequiredString" (list "global.credentials.mqttPassword" .Values.global.credentials.mqttPassword) -}}

{{- $gpu := default (dict) .Values.global.gpu -}}
{{- $gpuEnabled := or (default false (index $gpu "multimodalEmbeddingEnabled")) (default false (index $gpu "vdmsDataprepEnabled")) -}}
{{- if and $gpuEnabled (eq (trim (default "" (index $gpu "key"))) "") -}}
{{- fail "global.gpu.key must be set when GPU is enabled" -}}
{{- end -}}
{{- if and $gpuEnabled (eq (trim (default "" (index $gpu "device"))) "") -}}
{{- fail "global.gpu.device must be set when GPU is enabled" -}}
{{- end -}}
{{- end -}}
{{- define "live-video-search.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "live-video-search.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "live-video-search.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "live-video-search.labels" -}}
app.kubernetes.io/name: {{ include "live-video-search.name" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "live-video-search.selectorLabels" -}}
app.kubernetes.io/name: {{ include "live-video-search.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "live-video-search.vssTag" -}}
{{- default .Values.global.tag .Values.global.vssStackTag -}}
{{- end -}}

{{- define "live-video-search.smartNvrTag" -}}
{{- default .Values.global.tag .Values.global.smartNvrStackTag -}}
{{- end -}}

{{- define "live-video-search.image" -}}
{{- $registry := .registry | default "" -}}
{{- $repository := .repository -}}
{{- $tag := .tag -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" (trimSuffix "/" $registry) $repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}
{{- end -}}
