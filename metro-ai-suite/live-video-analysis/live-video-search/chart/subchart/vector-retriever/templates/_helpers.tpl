{{/*
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}
{{- define "lvs.vectorretriever.labels" -}}
app.kubernetes.io/name: vector-retriever
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "lvs.vectorretriever.tag" -}}
{{- default .Values.global.tag .Values.global.vssStackTag -}}
{{- end -}}

{{- define "lvs.vectorretriever.image" -}}
{{- $backend := lower (.Values.global.vectordbBackend | default "vdms") -}}
{{- $repository := .Values.image.repository | default (printf "vector-retriever-%s" $backend) -}}
{{- $tag := include "lvs.vectorretriever.tag" . -}}
{{- if .Values.global.registry -}}
{{ trimSuffix "/" .Values.global.registry }}/{{ $repository }}:{{ $tag }}
{{- else -}}
intel/{{ $repository }}:{{ $tag }}
{{- end -}}
{{- end -}}
