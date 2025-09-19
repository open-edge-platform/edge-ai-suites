# How to create a new sample app

This guide provides step-by-step instructions on how one can create a new
sample app by taking `Wind Turbine Anomaly Detection` Sample Application as a reference
by configuring the generic `Time Series AI Stack` as per the [how it works](./how-it-works.md).
Create a copy of the `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection`
folder and replace with the sample app name to be created.

## Steps to follow

### Configuration

#### 1. **Data Simulators/Destinations**:
   
   Options available:
   1. Update the OPC-UA/MQTT simulator containers (`edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/simulator`) as needed
      to ingest the needed dataset to analyze via a CSV file
   2. If you have existing `OPC-UA/MQTT` simulators, you can use that too. Just model the compose and helm template files like
      the way it's done for the above existing OPC-UA/MQTT simulators
   3. Directly configure `Telegraf` to connect to the device acting as `OPC-UA` server OR `MQTT publisher/broker`.
      Refer to the [Telegraf plugin documentation](https://docs.influxdata.com/telegraf/v1/plugins/#input-plugins/) for more details

#### 2. **Generic Time Series AI stack**

- **Data Ingestion - Telegraf**

    Update the `[[inputs.mqtt_consumer]]` and `[[inputs.opcua]]` sections in `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/telegraf-config/Telegraf.conf`, based on the MQTT/OPC-UA configuration, the input
    would be read and the topics in MQTT input plugin and name_override in OPC-UA
    input plugin is used for writing this as measurement in InfluxDB.

    In the above same conf file, the two `[[outputs.influxdb]]` plugins publish the 
    data to InfluxDB and Time Series Analytics microservice

- **Data Processing - Time Series Analytics Microservice**

    The `tick_scripts`, `models` and `udfs` folders at `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config` constitutes the User Defined Function (UDF) deployment package. The `config.json` at the same location is the Time Series microservice configuration.

    More details at [how-to-configure-custom-udf](./how-to-configure-custom-udf.md)

- **Data Visualization - Grafana**
  
    Prepare the custom grafana dashboard (`edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/grafana/dashboards`) and volume mount it by referring the grafana microservice at `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/docker-compose.yml`. For helm deployment,
    refer `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/helm/templates/grafana.yaml` file.

### Deployment

1. For docker compose deployment, follow the guide [Get Started](./get-started.md)
2. For helm deployment, follow the guide [How to deploy with helm](./how-to-deploy-with-helm.md)