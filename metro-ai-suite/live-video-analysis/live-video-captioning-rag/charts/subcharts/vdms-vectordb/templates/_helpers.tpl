{{/*
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{/* Expand the name of the chart. */}}
{{- define "vdms-vectordb.name" -}}
{{- default .Chart.Name .Values.nameOverride | lower | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Create a default fully qualified app name. */}}
{{- define "vdms-vectordb.fullname" -}}
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

{{/* Create chart label value (name-version). */}}
{{- define "vdms-vectordb.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | lower | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Common labels. */}}
{{- define "vdms-vectordb.labels" -}}
helm.sh/chart: {{ include "vdms-vectordb.chart" . }}
{{ include "vdms-vectordb.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ .Values.global.partOf | default "live-video-captioning" }}
{{- end }}

{{/* Selector labels. */}}
{{- define "vdms-vectordb.selectorLabels" -}}
app.kubernetes.io/name: {{ include "vdms-vectordb.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
