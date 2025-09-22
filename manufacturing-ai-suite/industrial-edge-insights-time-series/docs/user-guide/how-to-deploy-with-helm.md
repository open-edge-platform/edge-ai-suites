# Deploy with Helm

This guide provides step-by-step instructions for deploying the Wind Turbine Anomaly Detection sample application using Helm.

## Prerequisites

- [System Requirements](system-requirements.md)
-  K8s installation on single or multi node must be done as prerequisite to continue the following deployment. Note: The Kubernetes cluster is set up with `kubeadm`, `kubectl` and `kubelet` packages on single and multi nodes with `v1.30.2`.
  Refer to tutorials such as <https://adamtheautomator.com/installing-kubernetes-on-ubuntu> and many other
  online tutorials to setup kubernetes cluster on the web with host OS as Ubuntu 22.04.
- For Helm installation, refer to [helm website](https://helm.sh/docs/intro/install/)

> **Note**
> If Ubuntu Desktop is not installed on the target system, follow the instructions from Ubuntu to [install Ubuntu desktop](https://ubuntu.com/tutorials/install-ubuntu-desktop). The target system refers to the system where you are installing the application.

## Step 1: Generate or download the Helm charts

You can either generate or download the Helm charts.

- To download the Helm charts:

    Follow this procedure on the target system to install the package.

    1. Download Helm chart with the following command:

        `helm pull oci://registry-1.docker.io/intel/wind-turbine-anomaly-detection-sample-app --version 1.0.0`

    2. unzip the package using the following command:

        `tar -xvzf wind-turbine-anomaly-detection-sample-app-1.0.0.tgz`

    - Get into the Helm directory:

        `cd wind-turbine-anomaly-detection-sample-app`

- To generate the Helm charts:
   
    ```bash
    cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series # path relative to git clone folder
    make gen_helm_charts
    cd helm/
    ```

## Step 2: Configure and update the environment variables

1. Update the following fields in `values.yaml` file of the helm chart

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

## Step 3: Install Helm charts 

To install Helm charts, use one of the following options:

> **Note:**
> 1. Uninstall the Helm charts if already installed.
> 2. Note the `helm install` command fails if the above required fields are not populated
>    as per the rules called out in `values.yaml` file.

- OPC-UA ingestion flow:

    ```bash
    helm install ts-wind-turbine-anomaly --set env.TELEGRAF_INPUT_PLUGIN=opcua . -n ts-sample-app --create-namespace
    ```

- MQTT ingestion flow:

    ```bash
    helm install ts-wind-turbine-anomaly --set env.TELEGRAF_INPUT_PLUGIN=mqtt_consumer . -n ts-sample-app --create-namespace
    ```
Use the following command to verify if all the application resources got installed w/ their status:

```bash
   kubectl get all -n ts-sample-app
```

## Step 4: Copy the windturbine_anomaly_detection udf package for helm deployment to Time Series Analytics Microservice

To copy your own or existing model into Time Series Analytics Microservice in order to run this sample application in Kubernetes environment:

1. The following udf package is placed in the repository under `time_series_analytics_microservice`. 

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
    export SAMPLE_APP="wind-turbine-anomaly-detection"
    cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection # path relative to git clone folder
    cd time-series-analytics-config
    mkdir -p $SAMPLE_APP
    cp -r models tick_scripts udfs $SAMPLE_APP/.

    POD_NAME=$(kubectl get pods -n ts-sample-app -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-time-series-analytics-microservice | head -n 1)

    kubectl cp $SAMPLE_APP $POD_NAME:/tmp/ -n ts-sample-app
    ```
   > **Note:**  
   > Run the commands only after performing the Helm install.

## Step 5: Activate the New UDF Deployment Package

Run the following command to activate the UDF deployment package:
```sh
curl -k -X 'GET' \
  'https://<HOST_IP>:30001/ts-api/config?restart=true' \
  -H 'accept: application/json'
```

## Step 6: Verify the Wind Turbine Anomaly Detection Results

To verify the Wind Turbine Anomaly Detection Results, follow the steps [here](get-started.md#verify-the-wind-turbine-anomaly-detection-results).

## Uninstall Helm Charts

To uninstall Helm charts:

```sh
helm uninstall ts-wind-turbine-anomaly -n ts-sample-app
kubectl get all -n ts-sample-app # It may take a few minutes for all application resources to be cleaned up.
```

## Configure Alerts in Time Series Analytics Microservice

To configure alerts in Time Series Analytics Microservice, follow the steps [here](./how-to-configure-alerts.md#helm-deployment).

## Deploy the Application with a Custom UDF

To deploy the application with a custom UDF, follow the steps [here](./how-to-configure-custom-udf.md#helm-deployment).

## Deploy the Application with a Custom UDF by Uploading to the Model Registry

To deploy a custom UDF by uploading it to the Model Registry, follow the steps [here](./how-to-configure-custom-udf.md#with-model-registry).

## Troubleshooting

- Check pod details or container logs to diagnose failures:
    ```sh
    kubectl get pods -n ts-sample-app
    kubectl describe pod <pod_name> -n ts-sample-app # Shows details of the pod
    kubectl logs -f <pod_name> -n ts-sample-app # Shows logs of the container in the pod
    ```
