# Copyright Intel Corporation
#!/bin/bash -e

cp -f grafana/dashboards/*.json helm/
cp -f grafana/dashboards/*.yml helm/
cp -f influxdb/config/*.conf helm/
cp -f influxdb/init-influxdb.sh helm/
cp -f ../../tools/mqtt/broker/config/*.conf helm/
cp -f telegraf/config/*.conf helm
cp -f grafana/entrypoint.sh helm/grafana_entrypoint.sh
cp -f time_series_analytics_microservice/config.json helm/
sudo mkdir -p /opt/intel/time_series_analytics_microservice
sudo cp -rf time_series_analytics_microservice/udfs /opt/intel/time_series_analytics_microservice
sudo cp -rf time_series_analytics_microservice/tick_scripts /opt/intel/time_series_analytics_microservice
sudo cp -rf time_series_analytics_microservice/models /opt/intel/time_series_analytics_microservice
cp -f telegraf/entrypoint.sh helm/telegraf_entrypoint.sh
cd ../../tools/k8s_secrets
cp ../cert_gen.sh .
cp ../san.cnf .
docker build -f Dockerfile -t ia-cert-generator:1.0.0 .
rm cert_gen.sh san.cnf


