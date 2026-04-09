{{/*
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{- define "mediamtx.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "mediamtx.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "mediamtx.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "mediamtx.labels" -}}
helm.sh/chart: {{ include "mediamtx.chart" . }}
{{ include "mediamtx.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: live-video-captioning
{{- end }}

{{- define "mediamtx.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mediamtx.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
