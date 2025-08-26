{{/*
Template for Scene wait-for-db-ready init container script
*/}}
{{- define "scene.wait-for-db-script" -}}
echo "Waiting for DB via smart-intersection-web...";
until curl --insecure -s https://smart-intersection-web/api/v1/database-ready | grep 'true'; do
  echo "Database not ready yet...";
  sleep 5;
done;
echo "Database is ready!"
{{- end -}}
