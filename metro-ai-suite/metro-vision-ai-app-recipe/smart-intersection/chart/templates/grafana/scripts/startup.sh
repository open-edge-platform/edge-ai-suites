# This file contains a Helm template that generates the Grafana startup script.
# ShellCheck reports syntax errors (SC1054/SC1127) on the Helm template
# directives because they are not valid shell syntax when analyzed directly.
# These findings are expected and cannot be removed without changing the
# Helm template structure. The generated startup script is valid shell code
# and should be ShellChecked after Helm template rendering.
#shellcheck disable=SC1054,SC1127
{{/*
Template for Grafana startup script
*/}}
{{- define "grafana.startup-script" -}}
mkdir -p /var/lib/grafana/dashboards &&
cp /custom/anthem-intersection.json /var/lib/grafana/dashboards/anthem-intersection.json &&
mkdir -p /etc/grafana/provisioning/dashboards &&
cp /custom/dashboards.yml /etc/grafana/provisioning/dashboards/main.yml &&
mkdir -p /etc/grafana/provisioning/datasources &&
cp /custom/datasources.yml /etc/grafana/provisioning/datasources/datasources.yml &&
sed -i "s/<influx-api-token>/$(cat /custom/secrets/influxdb2-admin-token)/g" /etc/grafana/provisioning/datasources/datasources.yml &&
/run.sh
{{- end -}}
