{{/*
Expand the name of the chart.
*/}}
{{- define "vlmOpenvinoServing.name" -}}
  {{- default .Chart.Name (default "" .Values.vlmOpenvinoServing.name) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a fully qualified app name.
*/}}
{{- define "vlmOpenvinoServing.fullname" -}}
  {{- $name := default .Chart.Name (default "" .Values.vlmOpenvinoServing.name) -}}
  {{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Expand the name of the chart.
*/}}
{{- define "dataprepVisualdataMilvus.name" -}}
  {{- default .Chart.Name (default "" .Values.dataprepVisualdataMilvus.name) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a fully qualified app name.
*/}}
{{- define "dataprepVisualdataMilvus.fullname" -}}
  {{- $name := default .Chart.Name (default "" .Values.dataprepVisualdataMilvus.name) -}}
  {{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Expand the name of the chart.
*/}}
{{- define "retrieverMilvus.name" -}}
  {{- default .Chart.Name (default "" .Values.retrieverMilvus.name) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a fully qualified app name.
*/}}
{{- define "retrieverMilvus.fullname" -}}
  {{- $name := default .Chart.Name (default "" .Values.retrieverMilvus.name) -}}
  {{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Expand the name of the chart.
*/}}
{{- define "visualSearchQaApp.name" -}}
  {{- default .Chart.Name (default "" .Values.visualSearchQaApp.name) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a fully qualified app name.
*/}}
{{- define "visualSearchQaApp.fullname" -}}
  {{- $name := default .Chart.Name (default "" .Values.visualSearchQaApp.name) -}}
  {{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Expand the name of the chart.
*/}}
{{- define "multimodalembeddingServing.name" -}}
  {{- default .Chart.Name (default "" .Values.multimodalembeddingServing.name) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a fully qualified app name.
*/}}
{{- define "multimodalembeddingServing.fullname" -}}
  {{- $name := default .Chart.Name (default "" .Values.multimodalembeddingServing.name) -}}
  {{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}