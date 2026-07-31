{{/*
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{- define "mqtt.fullname" -}}
{{- printf "%s-mqtt" .Release.Name | lower | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "mqtt.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | lower | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: mqtt
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ .Values.global.partOf | default "live-video-alert-agent" }}
{{- end }}

{{- define "mqtt.serviceAccountName" -}}
{{- if .Values.global.serviceAccount.create }}{{ include "mqtt.fullname" . }}-sa{{- else }}default{{- end }}
{{- end }}

{{/*
Build a fully-qualified image reference.
When registry is set, uses "<registry>/<repository>:<tag>".
When registry is empty, defaults to docker.io/<repository>:<tag>.
*/}}
{{- define "mqtt.image" -}}
{{- $registry := .registry | default "" -}}
{{- $repository := .repository -}}
{{- $tag := .tag -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" (trimSuffix "/" $registry) $repository $tag -}}
{{- else -}}
{{- printf "docker.io/%s:%s" $repository $tag -}}
{{- end -}}
{{- end -}}
