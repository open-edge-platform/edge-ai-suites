# This file contains a Helm template that generates the scenescape startup script.
# ShellCheck reports syntax errors (SC1054/SC1127) on the Helm template
# directives because they are not valid shell syntax when analyzed directly.
# These findings are expected and cannot be removed without changing the
# Helm template structure. The generated startup script is valid shell code
# and should be ShellChecked after Helm template rendering.
#shellcheck disable=SC1054,SC1127
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
/home/scenescape/Scenescape/controller-cmd --resturl https://web.scenescape.intel.com/api/v1 --restauth=/tmp/secrets/controller.auth --broker broker.scenescape.intel.com --brokerauth /tmp/secrets/controller.auth --rootcert /tmp/secrets/scenescape-ca.pem --ntp ntpserv
{{- end -}}