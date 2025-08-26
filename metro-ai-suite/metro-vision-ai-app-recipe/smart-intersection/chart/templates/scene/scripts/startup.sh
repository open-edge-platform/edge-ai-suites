{{/*
Template for Scene controller startup script
*/}}
{{- define "scene.startup-script" -}}
echo $SMART_INTERSECTION_BROKER_SERVICE_HOST    broker.scenescape.intel.com >> /etc/hosts &&
echo $SMART_INTERSECTION_WEB_SERVICE_HOST    web.scenescape.intel.com >> /etc/hosts &&
mkdir -p /tmp/secrets/django &&
cp /tmp/secrets_/secrets.py /tmp/secrets/django/secrets.py &&
cp /tmp/secrets_/scenescape-ca.pem /tmp/secrets/scenescape-ca.pem &&
cp /tmp/secrets_/controller.auth /tmp/secrets/controller.auth &&
sed -i 's+RUNSECRETS=/run/secrets+RUNSECRETS=/tmp/secrets+g' /usr/local/bin/controller-init &&
sed -i '/touch \/tmp\/healthy/d' /usr/local/bin/controller-init &&
sed -i 's|--brokerauth ${BROKERAUTH}|--brokerauth ${BROKERAUTH} --rootcert ${BROKERROOTCERT}|g' /usr/local/bin/controller-init &&
/usr/local/bin/controller-init controller --broker broker.scenescape.intel.com --brokerrootcert /tmp/secrets/scenescape-ca.pem --ntp ntpserv
{{- end -}}
