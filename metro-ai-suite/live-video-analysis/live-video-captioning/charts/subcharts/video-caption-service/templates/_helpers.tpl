{{/*
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{- define "video-caption-service.name" -}}
{{- default .Chart.Name .Values.nameOverride | lower | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "video-caption-service.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | lower | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | lower | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | lower | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "video-caption-service.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | lower | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "video-caption-service.labels" -}}
helm.sh/chart: {{ include "video-caption-service.chart" . }}
{{ include "video-caption-service.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ .Values.global.partOf | default "live-video-captioning" }}
{{- end }}

{{- define "video-caption-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "video-caption-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "video-caption-service.modelsPvcName" -}}
{{- if .Values.modelsPvcName }}
{{- .Values.modelsPvcName }}
{{- else }}
{{- printf "%s-live-video-captioning-models" .Release.Name }}
{{- end }}
{{- end }}

{{- define "video-caption-service.detectionModelsPvcName" -}}
{{- if .Values.detectionModelsPvcName }}
{{- .Values.detectionModelsPvcName }}
{{- else }}
{{- printf "%s-live-video-captioning-detection-models" .Release.Name }}
{{- end }}
{{- end }}
