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

        `cd wind-turbine-anomaly-detection-sample-app-1.0.0`

- Generate the helm charts
   
    ```bash
    make gen_helm_charts
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
    http_proxy: # example: http_proxy: http://proxy.example.com:891
    https_proxy: # example: http_proxy: http://proxy.example.com:891
    ```

## Install helm charts - use only one of the options below:

> **Note:**
> 1. Please uninstall the helm charts if already installed.
> 2. If the worker nodes are running behind proxy server, then please additionally set env.HTTP_PROXY and env.HTTPS_PROXY env like the way env.TELEGRAF_INPUT_PLUGIN is being set below with helm install command

- OPC-UA ingestion flow:

    ```bash
    helm install ts-wind-turbine-anomaly --set env.TELEGRAF_INPUT_PLUGIN=opcua . -n apps --create-namespace
    ```

- MQTT ingestion flow:

    ```bash
    helm install ts-wind-turbine-anomaly --set env.TELEGRAF_INPUT_PLUGIN=mqtt_consumer . -n apps --create-namespace
    ```
Use the following command to verify if all the application resources got installed w/ their status:

```bash
   kubectl get all -n apps
```

## Verify the wind turbine anomaly detection results

Please follow the steps per helm deployment at [link](get-started.md#verify-the-wind-turbine-anomaly-detection-results)

## Uninstall helm charts

```bash
helm uninstall ts-wind-turbine-anomaly -n apps
kubectl get all -n apps # it takes few mins to have all application resources cleaned up
```

## Troubleshooting

- Check pod details or container logs to catch any failures:
 
  ```bash
  kubectl get pods -n apps
  kubectl describe pod <pod_name> -n apps # shows details of the pod
  kubectl logs -f <pod_name> -n apps # shows logs of the container in the pod
  ```