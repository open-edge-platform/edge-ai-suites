{{/*
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{- define "dlstreamer-pipeline-server.name" -}}
{{- default .Chart.Name .Values.nameOverride | lower | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "dlstreamer-pipeline-server.fullname" -}}
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

{{- define "dlstreamer-pipeline-server.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | lower | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "dlstreamer-pipeline-server.labels" -}}
helm.sh/chart: {{ include "dlstreamer-pipeline-server.chart" . }}
{{ include "dlstreamer-pipeline-server.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ .Values.global.partOf | default "live-video-captioning" }}
{{- end }}

{{- define "dlstreamer-pipeline-server.selectorLabels" -}}
app.kubernetes.io/name: {{ include "dlstreamer-pipeline-server.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Derive the models PVC name.
If modelsPvcName is explicitly set use it; otherwise construct the parent-chart default.
*/}}
{{- define "dlstreamer-pipeline-server.modelsPvcName" -}}
{{- if .Values.modelsPvcName }}
{{- .Values.modelsPvcName }}
{{- else }}
{{- printf "%s-live-video-captioning-models" .Release.Name }}
{{- end }}
{{- end }}

{{- define "dlstreamer-pipeline-server.detectionModelsPvcName" -}}
{{- if .Values.detectionModelsPvcName }}
{{- .Values.detectionModelsPvcName }}
{{- else }}
{{- printf "%s-live-video-captioning-detection-models" .Release.Name }}
{{- end }}
{{- end }}
