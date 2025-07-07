# How to Deploy with Helm

## Prerequisites

- [System Requirements](system-requirements.md)
-  K8s installation on single or multi node must be done as pre-requisite to continue the following deployment. Note: The kubernetes cluster is set up with `kubeadm`, `kubectl` and `kubelet` packages on single and multi nodes with `v1.30.2`.
  Refer to tutorials such as <https://adamtheautomator.com/installing-kubernetes-on-ubuntu> and many other
  online tutorials to setup kubernetes cluster on the web with host OS as ubuntu 22.04.
- For helm installation, refer to [helm website](https://helm.sh/docs/intro/install/)

> **Note**
> If Ubuntu Desktop is not installed on the target system, follow the instructions from Ubuntu to [install Ubuntu desktop](https://ubuntu.com/tutorials/install-ubuntu-desktop).

## Generate or Download the helm charts

- Using pre-built helm charts:

    Follow this procedure on the target system to install the package.

    1. Download helm chart with the following command

        `helm pull oci://<path-to-internal-harbor-registry-OR-intel-docker-hub-registry-path>/wind-turbine-anomaly-detection-sample-app --version 1.0.0`

    2. unzip the package using the following command

        `tar -xvzf wind-turbine-anomaly-detection-sample-app-1.0.0.tgz`

    - Get into the helm directory

        `cd wind-turbine-anomaly-detection-sample-app`

- Generate the helm charts
   
    ```bash
    cd edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection # path relative to git clone folder
    make gen_helm_charts
    cd helm/
    ```

## Configure and update the environment variables

1. Update the below fields in `values.yaml` file in the helm chart

    ``` sh
    INFLUXDB_USERNAME:
    INFLUXDB_PASSWORD:
    VISUALIZER_GRAFANA_USER:
    VISUALIZER_GRAFANA_PASSWORD:
    POSTGRES_PASSWORD:
    MINIO_ACCESS_KEY:  
    MINIO_SECRET_KEY: 
    HTTP_PROXY: # example: http_proxy: http://proxy.example.com:891
    HTTPS_PROXY: # example: http_proxy: http://proxy.example.com:891
    ```

## Install helm charts - use only one of the options below:

> **Note:**
> 1. Please uninstall the helm charts if already installed.
> 2. Please note the `helm install` command fails if the above required fields are not populated
>    as per the rules called out in `values.yaml` file.

- OPC-UA ingestion flow:

    ```bash
    helm install ts-wind-turbine-anomaly --set env.TELEGRAF_INPUT_PLUGIN=opcua . -n ts-wind-turbine-anomaly-app --create-namespace
    ```

- MQTT ingestion flow:

    ```bash
    helm install ts-wind-turbine-anomaly --set env.TELEGRAF_INPUT_PLUGIN=mqtt_consumer . -n ts-wind-turbine-anomaly-app --create-namespace
    ```
Use the following command to verify if all the application resources got installed w/ their status:

```bash
   kubectl get all -n ts-wind-turbine-anomaly-app
```

## Copy the windturbine_anomaly_detection udf package for helm deployment to Time Series Analytics Microservice

You need to copy your own or existing model into Time Series Analytics Microservice in order to run this sample application in Kubernetes environment:

1. The udf package is placed as below in the repository under `time_series_analytics_microservice`. 

    ```
    - time_series_analytics_microservice/
        - models/
            - windturbine_anomaly_detector.pkl
        - tick_scripts/
            - windturbine_anomaly_detector.tick
        - udfs/
            - requirements.txt
            - windturbine_anomaly_detector.py
    ```

2. Copy your new UDF package (using the windturbine anomaly detection UDF package as an example) to the `time-series-analytics-microservice` pod:
    ```sh
    cd edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection # path relative to git clone folder
    cd time_series_analytics_microservice
    mkdir windturbine_anomaly_detector
    cp -r models tick_scripts udfs windturbine_anomaly_detector/.

    POD_NAME=$(kubectl get pods -n ts-wind-turbine-anomaly-app -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-time-series-analytics-microservice | head -n 1)

    kubectl cp windturbine_anomaly_detector $POD_NAME:/tmp/ -n ts-wind-turbine-anomaly-app
    ```
   > **Note:**  
   > Run the above commands only after performing the Helm install.

## Activate the New UDF Deployment Package

Run the following command to activate the UDF deployment package:
```sh
curl -X 'GET' \
  'http://<HOST_IP>:30002/config?restart=true' \
  -H 'accept: application/json'
```

## Verify the Wind Turbine Anomaly Detection Results

Follow the steps in the Helm deployment guide at [this link](get-started.md#verify-the-wind-turbine-anomaly-detection-results).

## Uninstall Helm Charts

```sh
helm uninstall ts-wind-turbine-anomaly -n ts-wind-turbine-anomaly-app
kubectl get all -n ts-wind-turbine-anomaly-app # It may take a few minutes for all application resources to be cleaned up.
```


### Deploy the Application with OPC-UA Alerts

#### Prerequisite

Ensure the Wind Turbine Anomaly Detection sample app is deployed using the [installation step](#install-helm-charts---use-only-one-of-the-options-below) for OPC-UA ingestion.

To enable OPC-UA alerts in the Time Series Analytics Microservice, follow these steps:

1. Configure the tick script by following [these instructions](./how-to-configure-alerts.md#1-configuring-opc-ua-alert-in-tick-script).

2. Copy the tick script using the following command:
    ```sh
    cd edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection # path relative to git clone folder
    cd time_series_analytics_microservice
    mkdir windturbine_anomaly_detector
    cp -r tick_scripts windturbine_anomaly_detector/.

    POD_NAME=$(kubectl get pods -n ts-wind-turbine-anomaly-app -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-time-series-analytics-microservice | head -n 1)

    kubectl cp windturbine_anomaly_detector $POD_NAME:/tmp/ -n ts-wind-turbine-anomaly-app
    ```

3. Make the following REST API call to the Time Series Analytics microservice. Note that the `mqtt` alerts key is replaced with the `opcua` key and its specific details:
    ```sh
    curl -X 'POST' \
    'http://<HOST_IP>:30002/config' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/json' \
    -d '{
      "model_registry": {
          "enable": false,
          "version": "1.0"
      },
      "udfs": {
          "name": "windturbine_anomaly_detector",
          "models": "windturbine_anomaly_detector.pkl"
      },
      "alerts": {
          "opcua": {
              "opcua_server": "opc.tcp://ia-opcua-server:4840/freeopcua/server/",
              "namespace": 1,
              "node_id": 2004
          }
      }
    }'
    ```

4. To subscribe to OPC-UA alerts, follow [these steps](./how-to-configure-alerts.md#subscribing-to-opc-ua-alerts-using-sample-opcua-subscriber).

---

### Deploy the Application with a Custom UDF

1. Update the UDF deployment package by following the instructions in [Configure Time Series Analytics Microservice with Custom UDF Deployment Package](./how-to-configure-custom-udf.md#configure-time-series-analytics-microservice-with-custom-udf-deployment-package).

2. Copy the updated UDF deployment package using the [steps above](#copy-the-windturbine_anomaly_detection-udf-package-for-helm-deployment-to-time-series-analytics-microservice).

3. Make the following REST API call to the Time Series Analytics microservice for the updated custom UDF:
    ```sh
    curl -X 'POST' \
    'http://<HOST_IP>:30002/config' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/json' \
    -d '{
      "model_registry": {
          "enable": false,
          "version": "1.0"
      },
      "udfs": {
          "name": "<custom_UDF>",
          "models": "<custom_UDF>.pkl"
      },
      "alerts": {
          "mqtt": {
              "mqtt_broker_host": "ia-mqtt-broker",
              "mqtt_broker_port": 1883,
              "name": "my_mqtt_broker"
          }
      }
    }'
    ```

4. Verify the logs of the Time Series Analytics Microservice:
    ```sh
    POD_NAME=$(kubectl get pods -n ts-wind-turbine-anomaly-app -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-time-series-analytics-microservice | head -n 1)
    kubectl logs -f -n ts-wind-turbine-anomaly-app $POD_NAME
    ```

### Deploy the Application with a Custom UDF by Uploading to the Model Registry

Follow [these steps](./how-to-configure-custom-udf.md#with-model-registry) to deploy a custom UDF by uploading it to the Model Registry.

## Troubleshooting

- Check pod details or container logs to diagnose failures:
    ```sh
    kubectl get pods -n ts-wind-turbine-anomaly-app
    kubectl describe pod <pod_name> -n ts-wind-turbine-anomaly-app # Shows details of the pod
    kubectl logs -f <pod_name> -n ts-wind-turbine-anomaly-app # Shows logs of the container in the pod
    ```
