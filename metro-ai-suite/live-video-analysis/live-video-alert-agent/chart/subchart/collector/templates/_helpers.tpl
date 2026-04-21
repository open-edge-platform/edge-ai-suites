{{/*
Copyright (C) 2025 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{- define "collector.fullname" -}}
{{- printf "%s-collector" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "collector.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: collector
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: live-video-alert-agent
{{- end }}

{{- define "collector.serviceAccountName" -}}
{{- if .Values.global.serviceAccount.create }}{{ include "collector.fullname" . }}-sa{{- else }}default{{- end }}
{{- end }}

{{/*
Proxy environment variables — values flow from the parent global section.
Chart uses camelCase for proxy keys (httpProxy, httpsProxy, noProxy) to follow
Helm conventions and avoid confusion with OS environment variables.
*/}}
{{- define "collector.proxyEnv" -}}
- name: http_proxy
  value: {{ .Values.global.proxy.httpProxy | default "" | quote }}
- name: HTTP_PROXY
  value: {{ .Values.global.proxy.httpProxy | default "" | quote }}
- name: https_proxy
  value: {{ .Values.global.proxy.httpsProxy | default "" | quote }}
- name: HTTPS_PROXY
  value: {{ .Values.global.proxy.httpsProxy | default "" | quote }}
- name: no_proxy
  value: {{ .Values.global.proxy.noProxy | default "" | quote }}
- name: NO_PROXY
  value: {{ .Values.global.proxy.noProxy | default "" | quote }}
{{- end }}
