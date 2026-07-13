{{/*
Copyright (C) 2025 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "stia.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "stia.fullname" -}}
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
{{- define "stia.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "stia.labels" -}}
helm.sh/chart: {{ include "stia.chart" . }}
{{ include "stia.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "stia.selectorLabels" -}}
app.kubernetes.io/name: {{ include "stia.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Define the fully qualified name for the traffic-agent.
The traffic-agent is the parent chart; its K8s resources are named {release}-traffic-agent.
*/}}
{{- define "stia.trafficAgent.fullname" -}}
{{ printf "%s-traffic-agent" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Define the fully qualified name for the OVMS subchart service.
Mirrors what the ovms subchart's fullname helper generates ({release}-ovms),
allowing the traffic-agent deployment to construct the VLM base URL.
*/}}
{{- define "stia.ovms.fullname" -}}
{{ printf "%s-ovms" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Define the fully qualified name for the Metrics Manager subchart service.
Mirrors what the metrics-manager subchart fullname helper generates.
*/}}
{{- define "stia.metricsManager.fullname" -}}
{{ printf "%s-metrics-manager" .Release.Name | trunc 47 | trimSuffix "-" }}
{{- end }}

{{/*
Define the name of the CA cert secret.
*/}}
{{- define "stia.caCertSecretName" -}}
{{- if .Values.tls.caCertSecretName }}
{{- .Values.tls.caCertSecretName }}
{{- else }}
{{- include "stia.fullname" . }}-ca-cert
{{- end }}
{{- end }}

{{/*
MQTT broker FQDN.
If .Values.mqtt.host is set, use it directly.
Otherwise, construct from serviceName + brokerNamespace.
If brokerNamespace is empty, default to the release namespace.
*/}}
{{- define "stia.mqttHost" -}}
{{- if .Values.mqtt.host }}
{{- .Values.mqtt.host }}
{{- else }}
{{- $ns := default .Release.Namespace .Values.mqtt.brokerNamespace }}
{{- printf "%s.%s.svc.cluster.local" .Values.mqtt.serviceName $ns }}
{{- end }}
{{- end }}
