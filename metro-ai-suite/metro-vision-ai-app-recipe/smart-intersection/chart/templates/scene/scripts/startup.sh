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
/home/scenescape/SceneScape/controller-cmd --resturl https://web.scenescape.intel.com/api/v1 --restauth=/tmp/secrets/controller.auth --broker broker.scenescape.intel.com --brokerauth /tmp/secrets/controller.auth --rootcert /tmp/secrets/scenescape-ca.pem --ntp ntpserv
{{- end -}}