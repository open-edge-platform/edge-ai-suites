{{/*
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{- define "smart-route-planning-agent.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "smart-route-planning-agent.fullname" -}}
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

{{- define "smart-route-planning-agent.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "smart-route-planning-agent.labels" -}}
helm.sh/chart: {{ include "smart-route-planning-agent.chart" . }}
{{ include "smart-route-planning-agent.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/* Selector labels — do not change after first install */}}
{{- define "smart-route-planning-agent.selectorLabels" -}}
app.kubernetes.io/name: {{ include "smart-route-planning-agent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}


{{/* Handles optional registry prefix without double slashes */}}
{{- define "smart-route-planning-agent.image" -}}
{{- if .Values.image.registry }}
{{- printf "%s/%s:%s" (.Values.image.registry | trimSuffix "/") .Values.image.repository .Values.image.tag }}
{{- else }}
{{- printf "%s:%s" .Values.image.repository .Values.image.tag }}
{{- end }}
{{- end }}
