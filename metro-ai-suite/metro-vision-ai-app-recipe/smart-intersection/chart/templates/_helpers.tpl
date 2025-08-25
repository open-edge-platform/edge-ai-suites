{{- define "requiredFile" -}}
{{- $root := index . 0 -}}
{{- $path := index . 1 -}}
{{- required (printf "Missing required file: %s" $path) ($root.Files.Get $path) -}}
{{- end -}}
