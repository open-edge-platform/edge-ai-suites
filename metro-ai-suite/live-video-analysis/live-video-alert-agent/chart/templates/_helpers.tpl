{{/*
Copyright (C) 2025 Intel Corporation
SPDX-License-Identifier: Apache-2.0
*/}}

{{- define "lva.validate" -}}
{{- if eq (trim (default "" .Values.global.externalIP)) "" -}}
{{- fail "global.externalIP must be set (use user_values_override.yaml or --set global.externalIP=<NODE_IP>)" -}}
{{- end -}}
{{- if and .Values.global.gpu.enabled (eq (trim (default "" .Values.global.gpu.key)) "") -}}
{{- fail "global.gpu.key must be set when global.gpu.enabled=true (e.g. gpu.intel.com/i915 or gpu.intel.com/xe)" -}}
{{- end -}}
{{- end -}}
{{- define "lva.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | lower | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: live-video-alert-agent
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: live-video-alert-agent
{{- end }}
