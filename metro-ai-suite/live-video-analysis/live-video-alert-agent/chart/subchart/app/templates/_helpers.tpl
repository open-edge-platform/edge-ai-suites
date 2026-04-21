{{/*
Copyright (C) 2025 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{- define "app.fullname" -}}
{{- printf "%s-live-video-alert-agent" .Release.Name | lower |trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "app.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | lower | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: live-video-alert-agent
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ .Values.global.partOf | default "live-video-alert-agent" }}
{{- end }}

{{- define "app.serviceAccountName" -}}
{{- if .Values.global.serviceAccount.create }}{{ include "app.fullname" . }}-sa{{- else }}default{{- end }}
{{- end }}

{{/*
Build a fully-qualified image reference.
When registry is set, uses "<registry>/<repository>:<tag>".
When registry is empty, defaults to docker.io/intel/<repository>:<tag> for
first-party images (no "/" in repo) and docker.io/<repository>:<tag> otherwise.
*/}}
{{- define "app.image" -}}
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
Note: Chart uses camelCase for proxy keys (httpProxy, httpsProxy, noProxy) to follow
Helm conventions and avoid confusion with OS environment variables. The template then
sets both lowercase and uppercase variants for maximum compatibility.
*/}}
{{- define "app.proxyEnv" -}}
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
