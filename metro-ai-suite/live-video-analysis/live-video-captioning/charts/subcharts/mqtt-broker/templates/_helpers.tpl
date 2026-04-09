{{/*
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{- define "mqtt-broker.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "mqtt-broker.fullname" -}}
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

{{- define "mqtt-broker.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "mqtt-broker.labels" -}}
helm.sh/chart: {{ include "mqtt-broker.chart" . }}
{{ include "mqtt-broker.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: live-video-captioning
{{- end }}

{{- define "mqtt-broker.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mqtt-broker.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
