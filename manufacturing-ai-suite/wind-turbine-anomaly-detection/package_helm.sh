#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
#!/bin/bash -e

cp -f grafana/dashboards/*.json helm/
cp -f grafana/dashboards/*.yml helm/
cp -f influxdb/config/*.conf helm/
cp -f influxdb/init-influxdb.sh helm/
cp -f mqtt-broker/*.conf helm/
cp -f simulator/simulation_data/windturbine_data.csv helm/
cp -f telegraf/config/*.conf helm
cp -f grafana/entrypoint.sh helm/grafana_entrypoint.sh
cp -f time_series_analytics_microservice/config.json helm/
cp -f telegraf/entrypoint.sh helm/telegraf_entrypoint.sh


