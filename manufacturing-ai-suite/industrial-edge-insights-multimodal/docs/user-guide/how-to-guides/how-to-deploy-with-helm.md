# Deploy with Helm

This guide provides step-by-step instructions for deploying the MultiModal - Weld Defect Detection sample application using Helm.

## Prerequisites

- [System Requirements](../get-started/system-requirements.md)
- K8s installation on single or multi node must be done as prerequisite to continue the following deployment. Note that the Kubernetes cluster is set up with `kubeadm`, `kubectl` and `kubelet` packages on single and multi nodes with `v1.30.2`.
 Refer to online tutorials (such as <https://adamtheautomator.com/install-kubernetes-ubuntu>) to setup kubernetes cluster on the web with host OS as Ubuntu 22.04.
- For Helm installation, refer to [helm website](https://helm.sh/docs/intro/install/)

> **Note:**
> If Ubuntu Desktop is not installed on the target system, follow the instructions from Ubuntu
> to [install Ubuntu desktop](https://ubuntu.com/tutorials/install-ubuntu-desktop). The target
> system refers to the system where you are installing the application.

## Step 1: Generate or download the Helm charts

You can either generate or download the Helm charts.

- To download the Helm charts:

  Follow this procedure on the target system to install the package.

  1. Download Helm chart with the following command:

     ```bash
     helm pull oci://registry-1.docker.io/intel/multimodal-weld-defect-detection-sample-app --version 1.0.0-weekly
     ```

  2. Unzip the package using the following command:

     ```bash
     tar -xvzf multimodal-weld-defect-detection-sample-app-1.0.0-weekly.tgz
     ```

- Get into the Helm directory:

  ```bash
  cd multimodal-weld-defect-detection-sample-app
  ```

- To generate the Helm charts:

  ```bash
  cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal # path relative to git clone folder

  make gen_helm_charts

  cd helm/
  ```

## Step 2: Configure and update the environment variables

1. Update the following fields in the `values.yaml` file of the helm chart.

   ```bash
   WORK_DIR: # Update with the absolute path to your industrial-edge-insights-multimodal directory
   INFLUXDB_USERNAME:
   INFLUXDB_PASSWORD:
   VISUALIZER_GRAFANA_USER:
   VISUALIZER_GRAFANA_PASSWORD:
   HTTP_PROXY:  # example: http_proxy: http://proxy.example.com:891
   HTTPS_PROXY:  # example: http_proxy: http://proxy.example.com:891
   MTX_WEBRTCICESERVERS2_0_USERNAME:
   MTX_WEBRTCICESERVERS2_0_PASSWORD:
   HOST_IP:  # IP address of server where DL Streamer Pipeline Server is running
   ```

## Step 3: Install Helm charts

> **Note:**
>
> 1. Uninstall Helm charts if already installed.
> 2. Note the `helm install` command fails if the above required fields are not populated
>    as per the rules called out in the `values.yaml` file.

To install Helm charts, use one of the following options:

```bash
helm install multimodal-weld-defect-detection . -n multimodal-sample-app --create-namespace
```

**Verify Installation:**

> **Note:**
> The `deployment-coturn`, `deployment-fusion-analytics`, `deployment-ia-weld-data-simulator` and `deployment-telegraf` pods might restart since its depended on `deployment-mqtt-broker` and `deployment-mediamtx`

Use the following command to verify if all the application resources got installed with their status:

```bash
kubectl get all -n multimodal-sample-app
```

## Step 4: Copy the udf package for helm deployment

**DL Streamer Pipeline Server**

To copy your own or existing model into DL Streamer Pipeline Server in order to run this sample application in Kubernetes environment:

The model package is available in the repository at `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal/configs/dlstreamer-pipeline-server/`.

Copy the resources such as video and model from local directory to the to the
`dlstreamer-pipeline-server` pod to make them available for application while launching pipelines.

```bash
cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal/configs/dlstreamer-pipeline-server/

POD_NAME=$(kubectl get pods -n multimodal-sample-app -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

kubectl cp models $POD_NAME:/home/pipeline-server/resources/ -c dlstreamer-pipeline-server -n multimodal-sample-app
```

**Time Series Analytics Microservice**

To copy your own or existing model into Time Series Analytics Microservice in order to run
this sample application in Kubernetes environment:

1. The following udf package is placed in the repository under `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal/configs/time-series-analytics-microservice`.

   ```text
   - time-series-analytics-microservice/
       - models/
           - weld_anomaly_detector.cb
       - tick_scripts/
           - weld_anomaly_detector.tick
       - udfs/
           - requirements.txt
           - weld_anomaly_detector.py
   ```

2. Copy your new UDF package to the `time-series-analytics-microservice` pod:

   ```bash
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal/configs/time-series-analytics-microservice # path relative to git clone folder
   mkdir -p weld_anomaly_detector
   cp -r models tick_scripts udfs weld_anomaly_detector/.

   POD_NAME=$(kubectl get pods -n multimodal-sample-app -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-time-series-analytics-microservice | head -n 1)

   kubectl cp weld_anomaly_detector $POD_NAME:/tmp/ -n multimodal-sample-app
   ```

> **Note:**
> Run the commands only after performing the Helm install.

## Step 5: Activate the Pipeline/UDF Deployment Package


**DL Streamer Pipeline Server**

You use a Client URL (cURL) command to start the pipeline. Start this pipeline with the
following cURL command.

```bash
curl -k https://localhost:30001/dsps-api/pipelines/user_defined_pipelines/weld_defect_classification -X POST -H 'Content-Type: application/json' -d '{
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "vision_weld_defect_classification"
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "samplestream"
        }
    },
    "parameters": {
        "classification-properties": {
            "model": "/home/pipeline-server/resources/models/weld-defect-classification-f16-DeiT/deployment/Classification/model/model.xml",
            "device": "CPU"
        }
    }
}'
```

**Time Series Analytics Microservice**

> **NOTE:** UDF inferencing on GPU is not supported.

Run the following command to activate the UDF deployment package:

```bash
curl -k -X 'GET' \
'https://localhost:30001/ts-api/config?restart=true' \
-H 'accept: application/json'
```

## Step 6: Verify the Results

Follow the verification steps in the [Get Started guide](../get-started.md#verify-the-weld-defect-detection-results)

## Uninstall Helm Charts

To uninstall Helm charts:

```bash
helm uninstall multimodal-weld-defect-detection -n multimodal-sample-app
kubectl get all -n multimodal-sample-app # It may take a few minutes for all application resources to be cleaned up.
```

## Configure Alerts in Time Series Analytics Microservice

To configure alerts in Time Series Analytics Microservice, follow [the steps](./how-to-configure-alerts.md#helm-deployment).

## Troubleshooting

- Check pod details or container logs to diagnose failures:

  ```bash
  kubectl get pods -n multimodal-sample-app
  kubectl describe pod <pod_name> -n multimodal-sample-app # Shows details of the pod
  kubectl logs -f <pod_name> -n multimodal-sample-app # Shows logs of the container in the pod
  ```
