{{/*
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "ovms.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "ovms.fullname" -}}
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

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ovms.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "ovms.labels" -}}
helm.sh/chart: {{ include "ovms.chart" . }}
{{ include "ovms.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "ovms.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ovms.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Compute the OVMS image reference, selecting GPU or CPU tag based on gpu.enabled.
*/}}
{{- define "ovms.image" -}}
{{- $targetDevice := ternary "GPU" .Values.env.targetDevice .Values.gpu.enabled -}}
{{- if contains "GPU" $targetDevice -}}
{{- printf "%s:%s" .Values.image.repository .Values.image.gpuTag -}}
{{- else -}}
{{- printf "%s:%s" .Values.image.repository .Values.image.tag -}}
{{- end }}
{{- end }}

{{/*
Compute the HuggingFace token Secret name.
*/}}
{{- define "ovms.hfTokenSecretName" -}}
{{- printf "%s-hf-token" (include "ovms.fullname" .) -}}
{{- end }}
