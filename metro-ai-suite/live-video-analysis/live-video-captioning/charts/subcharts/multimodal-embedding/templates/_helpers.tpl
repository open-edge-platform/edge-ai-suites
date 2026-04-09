{{/*
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{/* Expand the name of the chart. */}}
{{- define "multimodal-embedding.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Create a default fully qualified app name. */}}
{{- define "multimodal-embedding.fullname" -}}
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

{{/* Create chart label value (name-version). */}}
{{- define "multimodal-embedding.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Common labels. */}}
{{- define "multimodal-embedding.labels" -}}
helm.sh/chart: {{ include "multimodal-embedding.chart" . }}
{{ include "multimodal-embedding.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/* Selector labels. */}}
{{- define "multimodal-embedding.selectorLabels" -}}
app.kubernetes.io/name: {{ include "multimodal-embedding.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/* Backward-compatible alias used by legacy templates. */}}
{{- define "multimodal-embedding-ms.fullname" -}}
{{ include "multimodal-embedding.fullname" . }}
{{- end }}
