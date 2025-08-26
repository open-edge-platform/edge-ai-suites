{{/*
Template for Web server startup script
*/}}
{{- define "web.startup-script" -}}
echo $SMART_INTERSECTION_BROKER_SERVICE_HOST    broker.scenescape.intel.com >> /etc/hosts &&
echo $SMART_INTERSECTION_WEB_SERVICE_HOST    web.scenescape.intel.com >> /etc/hosts &&
mkdir -p /run/secrets/certs &&
mkdir -p /run/secrets/django &&
cp /tmp/secrets/secrets.py /run/secrets/django/secrets.py &&
cp /tmp/secrets/browser.auth /run/secrets/browser.auth &&
cp /tmp/secrets/controller.auth /run/secrets/controller.auth &&
cp /tmp/secrets/scenescape-ca.pem /run/secrets/certs/scenescape-ca.pem &&
cp /tmp/secrets/scenescape-web.crt /run/secrets/certs/scenescape-web.crt &&
cp /tmp/secrets/scenescape-web.key /run/secrets/certs/scenescape-web.key &&
cp /tmp/secrets/secrets.py /home/scenescape/SceneScape/manager/secrets.py &&
sed -i "s/'HOST': 'localhost'/'HOST':'smart-intersection-pgserver'/g" /home/scenescape/SceneScape/manager/settings.py &&
chown -R scenescape:scenescape /workspace &&
/usr/local/bin/scenescape-init webserver --dbhost smart-intersection-pgserver --broker broker.scenescape.intel.com --brokerauth /run/secrets/browser.auth --brokerrootcert /run/secrets/certs/scenescape-ca.pem
{{- end -}}
