# Copyright Intel Corporation
#!/bin/bash

cp -f grafana/dashboards/*.json helm/
cp -f grafana/dashboards/*.yml helm/
cp -f influxdb/config/*.conf helm/
cp -f ../../tools/mqtt/broker/config/*.conf helm/
cp -f telegraf/config/*.conf helm
cp -f grafana/entrypoint.sh helm/

