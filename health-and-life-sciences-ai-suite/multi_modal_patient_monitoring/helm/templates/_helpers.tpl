{{- define "health-ai.image" -}}
{{- $image := .image -}}
{{- if kindIs "map" $image -}}
{{- printf "%s/%s:%s" $image.registry $image.name $image.tag -}}
{{- else -}}
{{- $image -}}
{{- end -}}
{{- end }}
