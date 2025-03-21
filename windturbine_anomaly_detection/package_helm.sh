# Copyright Intel Corporation
#!/bin/bash -e

cp -f grafana/dashboards/*.json helm/
cp -f grafana/dashboards/*.yml helm/
cp -f influxdb/config/*.conf helm/
cp -f influxdb/init-influxdb.sh helm/
cp -f ../../tools/mqtt/broker/config/*.conf helm/
cp -f telegraf/config/*.conf helm
cp -f grafana/entrypoint.sh helm/grafana_entrypoint.sh
cp -f kapacitor/config.json helm/
cp -f telegraf/entrypoint.sh helm/telegraf_entrypoint.sh
cd ../../tools/k8s_secrets
cp ../cert_gen.sh .
cp ../san.cnf .
docker build -f Dockerfile -t ia-cert-generator:1.0.0 .
rm cert_gen.sh san.cnf


