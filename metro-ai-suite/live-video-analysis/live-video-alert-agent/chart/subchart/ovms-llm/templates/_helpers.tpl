{{/*
Copyright (C) 2025 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{- define "ovms-llm.fullname" -}}
{{- printf "%s-ovms-llm" .Release.Name | lower | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ovms-llm.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | lower | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: ovms-llm
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: live-video-alert-agent
{{- end }}

{{- define "ovms-llm.serviceAccountName" -}}
{{- if .Values.global.serviceAccount.create }}{{ include "ovms-llm.fullname" . }}-sa{{- else }}default{{- end }}
{{- end }}

{{/*
Build a fully-qualified image reference.
When registry is set, uses "<registry>/<repository>:<tag>".
When registry is empty, defaults to docker.io/<repository>:<tag>.
*/}}
{{- define "ovms-llm.image" -}}
{{- $registry := .registry | default "" -}}
{{- $repository := .repository -}}
{{- $tag := .tag -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" (trimSuffix "/" $registry) $repository $tag -}}
{{- else -}}
{{- printf "docker.io/%s:%s" $repository $tag -}}
{{- end -}}
{{- end -}}

{{/*
Proxy environment variables — values flow from the parent global section.
*/}}
{{- define "ovms-llm.proxyEnv" -}}
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
