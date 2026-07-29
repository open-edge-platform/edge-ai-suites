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
