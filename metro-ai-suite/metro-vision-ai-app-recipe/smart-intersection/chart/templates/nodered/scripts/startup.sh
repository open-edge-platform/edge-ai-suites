# This file contains a Helm template that generates the Node-RED startup script.
# ShellCheck reports syntax errors (SC1054/SC1127) on the Helm template
# directives because they are not valid shell syntax when analyzed directly.
# These findings are expected and cannot be removed without changing the
# Helm template structure. The generated startup script is valid shell code
# and should be ShellChecked after Helm template rendering.
#shellcheck disable=SC1054,SC1127
{{/*
Template for Node-RED startup script
*/}}
{{- define "nodered.startup-script" -}}
mkdir -p /data/nodered && \
cp /config/flows_cred.json /data/flows_cred.json && \
cp /config/settings.js /data/settings.js && \
cp /config/flows.json /data/flows.json && \
cp /config/install_package.sh /data/install_package.sh && \
cp -r /mosquitto/secrets /run/ && \
chmod +x /data/install_package.sh && \
sed -i "s/<influx-api-token>/$INFLUX_TOKEN/g" /data/flows_cred.json && \
echo "$SMART_INTERSECTION_BROKER_SERVICE_HOST    broker.scenescape.intel.com" >> /etc/hosts && \
/data/install_package.sh && \
chown -R node-red:node-red /data/nodered && \
chown -R node-red:node-red /data && \
/usr/src/node-red/entrypoint.sh
{{- end -}}
