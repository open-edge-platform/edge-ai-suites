{{/*
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0

_helpers.tpl — parent chart helpers.
All templates defined here with the "lvc." prefix are globally accessible
from every subchart, enabling shared patterns without duplication.
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "live-video-captioning.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "live-video-captioning.fullname" -}}
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
Create chart label value (name-version).
*/}}
{{- define "live-video-captioning.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common Helm-standard labels applied to every resource in the parent chart.
*/}}
{{- define "live-video-captioning.labels" -}}
helm.sh/chart: {{ include "live-video-captioning.chart" . }}
{{ include "live-video-captioning.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels (stable — never change after first install).
*/}}
{{- define "live-video-captioning.selectorLabels" -}}
app.kubernetes.io/name: {{ include "live-video-captioning.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- /*
════════════════════════════════════════════════════════════════
  SHARED GLOBAL HELPERS  (prefix: "lvc.")
  These are globally scoped and callable from every subchart.
════════════════════════════════════════════════════════════════
*/}}

{{/*
lvc.proxyEnv — emit proxy environment variables when proxy settings are
configured in global values.  Call from any subchart deployment template:

  env:
    {{- include "lvc.proxyEnv" . | nindent 12 }}

The helper reads from .Values.global.{httpProxy,httpsProxy,noProxy}.
Internal Kubernetes service hostnames are always prepended to no_proxy so
users only need to supply their RTSP camera hosts/IPs.
*/}}
{{- define "lvc.proxyEnv" -}}
{{- $internalNoProxy := "localhost,127.0.0.1,mqtt-broker,dlstreamer-pipeline-server,mediamtx,coturn,video-caption-service,live-metrics-service,collector" -}}
{{- if .Values.global.httpProxy }}
- name: http_proxy
  value: {{ .Values.global.httpProxy | quote }}
- name: HTTP_PROXY
  value: {{ .Values.global.httpProxy | quote }}
{{- end }}
{{- if .Values.global.httpsProxy }}
- name: https_proxy
  value: {{ .Values.global.httpsProxy | quote }}
- name: HTTPS_PROXY
  value: {{ .Values.global.httpsProxy | quote }}
{{- end }}
{{- if .Values.global.httpProxy }}
{{- $noProxy := $internalNoProxy -}}
{{- if .Values.global.noProxy -}}
  {{- $noProxy = printf "%s,%s" $internalNoProxy .Values.global.noProxy -}}
{{- end }}
- name: no_proxy
  value: {{ $noProxy | quote }}
- name: NO_PROXY
  value: {{ $noProxy | quote }}
{{- end }}
{{- end }}

{{/*
lvc.nodeAffinity — emit a requiredDuringScheduling nodeAffinity block that
pins pods to the node specified by global.nodeName (matched against the
built-in kubernetes.io/hostname label).

Usage (inside a pod spec, indented appropriately):

  {{- include "lvc.nodeAffinity" . | nindent 6 }}

Produces:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: kubernetes.io/hostname
            operator: In
            values:
            - "worker4"
*/}}
{{- define "lvc.nodeAffinity" -}}
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
            - key: "kubernetes.io/hostname"
              operator: In
              values:
                - {{ .Values.global.nodeName | quote }}
{{- end }}

{{/*
lvc.imagePullSecrets — emit imagePullSecrets list from global values.
Usage:
  {{- include "lvc.imagePullSecrets" . | nindent 6 }}
*/}}
{{- define "lvc.imagePullSecrets" -}}
{{- with .Values.global.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}
