{{/*
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{- define "alert-agent-service.fullname" -}}
{{- printf "%s-alert-agent-service" .Release.Name | lower | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "alert-agent-service.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | lower | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: alert-agent-service
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ .Values.global.partOf | default "live-video-alert-agent" }}
{{- end }}

{{- define "alert-agent-service.serviceAccountName" -}}
{{- if .Values.global.serviceAccount.create }}{{ include "alert-agent-service.fullname" . }}-sa{{- else }}default{{- end }}
{{- end }}

{{/*
Build a fully-qualified image reference.
When registry is set, uses "<registry>/<repository>:<tag>".
When registry is empty, defaults to docker.io/intel/<repository>:<tag> for
first-party images (no "/" in repo) and docker.io/<repository>:<tag> otherwise.
*/}}
{{- define "alert-agent-service.image" -}}
{{- $registry := .registry | default "" -}}
{{- $repository := .repository -}}
{{- $tag := .tag -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" (trimSuffix "/" $registry) $repository $tag -}}
{{- else -}}
{{- if contains "/" $repository -}}
{{- printf "docker.io/%s:%s" $repository $tag -}}
{{- else -}}
{{- printf "docker.io/intel/%s:%s" $repository $tag -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Proxy environment variables — values flow from the parent global section.
*/}}
{{- define "alert-agent-service.proxyEnv" -}}
{{- $noProxy := .Values.global.proxy.noProxy | default "" -}}
{{- $serviceNoProxy := printf "%s-ovms-llm,%s-mqtt" .Release.Name .Release.Name -}}
{{- $mergedNoProxy := ternary (printf "%s,%s" $noProxy $serviceNoProxy) $serviceNoProxy (ne $noProxy "") -}}
- name: http_proxy
  value: {{ .Values.global.proxy.httpProxy | default "" | quote }}
- name: HTTP_PROXY
  value: {{ .Values.global.proxy.httpProxy | default "" | quote }}
- name: https_proxy
  value: {{ .Values.global.proxy.httpsProxy | default "" | quote }}
- name: HTTPS_PROXY
  value: {{ .Values.global.proxy.httpsProxy | default "" | quote }}
- name: no_proxy
  value: {{ $mergedNoProxy | quote }}
- name: NO_PROXY
  value: {{ $mergedNoProxy | quote }}
{{- end }}
