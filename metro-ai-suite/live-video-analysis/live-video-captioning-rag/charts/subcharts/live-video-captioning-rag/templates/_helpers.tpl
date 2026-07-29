{{/*
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{/* Expand the name of the chart. */}}
{{- define "live-video-captioning-rag.name" -}}
{{- default .Chart.Name .Values.nameOverride | lower | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Create a default fully qualified app name. */}}
{{- define "live-video-captioning-rag.fullname" -}}
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
{{- define "live-video-captioning-rag.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | lower | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Common labels. */}}
{{- define "live-video-captioning-rag.labels" -}}
helm.sh/chart: {{ include "live-video-captioning-rag.chart" . }}
{{ include "live-video-captioning-rag.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ .Values.global.partOf | default "live-video-captioning" }}
{{- end }}

{{/* Selector labels. */}}
{{- define "live-video-captioning-rag.selectorLabels" -}}
app.kubernetes.io/name: {{ include "live-video-captioning-rag.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/* Derive the models PVC name if no override is provided. */}}
{{- define "live-video-captioning-rag.modelsPvcName" -}}
{{- if .Values.modelsPvcName }}
{{- .Values.modelsPvcName }}
{{- else }}
{{- printf "%s-live-video-captioning-models" .Release.Name }}
{{- end }}
{{- end }}
