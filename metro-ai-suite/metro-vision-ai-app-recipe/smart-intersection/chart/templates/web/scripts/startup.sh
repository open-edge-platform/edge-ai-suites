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
printf '\n# CSRF and reverse proxy configuration for Helm deployment\nCSRF_TRUSTED_ORIGINS = [\n    "https://localhost",\n    "https://nginx-reverse-proxy",\n    "http://localhost",\n    "http://nginx-reverse-proxy",\n    "https://127.0.0.1",\n    "http://127.0.0.1",\n    "https://localhost:30443",\n    "http://localhost:30080",\n    "https://127.0.0.1:30443",\n    "http://127.0.0.1:30080",\n    "https://localhost:443",\n    "http://localhost:80",\n    "https://{{ .Values.global.externalIP }}:30443",\n    "http://{{ .Values.global.externalIP }}:30080",\n    "https://{{ .Values.global.externalIP }}",\n    "http://{{ .Values.global.externalIP }}"\n]\nALLOWED_HOSTS = ["*"]\nSECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")\nUSE_X_FORWARDED_HOST = True\nUSE_X_FORWARDED_PORT = True\nCSRF_COOKIE_SECURE = False\nCSRF_COOKIE_HTTPONLY = False\nSESSION_COOKIE_SECURE = False\nCSRF_COOKIE_SAMESITE = "Lax"\nSESSION_COOKIE_SAMESITE = "Lax"\n' >> /home/scenescape/SceneScape/manager/settings.py &&
chown -R scenescape:scenescape /workspace &&
/usr/local/bin/scenescape-init webserver --dbhost smart-intersection-pgserver --broker broker.scenescape.intel.com --brokerauth /run/secrets/browser.auth --brokerrootcert /run/secrets/certs/scenescape-ca.pem
{{- end -}}
