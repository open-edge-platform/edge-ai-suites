# How to Deploy with Helm

This section provides step-by-step instructions for deploying the Loitering Detection application using Helm.

The estimated time to complete this procedure is **30 minutes**.

## Get Started

Complete this section to confirm that your setup is working correctly and try out workflows in the sample application.

## Prerequisites

- [System Requirements](system-requirements.md)
-  K8s installation on single or multi node must be done as pre-requisite to continue the following deployment. Note: The kubernetes cluster is set up with `kubeadm`, `kubectl` and `kubelet` packages on single and multi nodes with `v1.30.2`.
  Refer to tutorials such as <https://adamtheautomator.com/installing-kubernetes-on-ubuntu> and many other
  online tutorials to setup kubernetes cluster on the web with host OS as ubuntu 22.04.
- For Helm installation, refer to [helm website](https://helm.sh/docs/intro/install/)

> **Note**
> If Ubuntu Desktop is not installed on the target system, follow the instructions from Ubuntu to [install Ubuntu desktop](https://ubuntu.com/tutorials/install-ubuntu-desktop).

## Step 1: Download the Helm chart

Follow this procedure on the target system to download the package.

**Note**: Skip this step if you have already followed the steps as part of the [Get Started guide](./get-started.md).

Before you can deploy with Helm, you must clone the repository and download the helm chart:

```bash
# Clone the repository
git clone https://github.com/open-edge-platform/edge-ai-suites.git

# Navigate to the Metro AI Suite directory
cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/

```

## Step 2: Configure and update the environment variables

1. Update the following fields in `values.yaml` file in the Helm chart:

    ```bash
        # Edit the values.yml file to add proxy configuration
        nano ./loitering-detection/helm-chart/values.yaml
    ```

    ``` sh
    HOST_IP: # replace localhost with system IP example: HOST_IP: 10.100.100.100
    http_proxy: # example: http_proxy: http://proxy.example.com:891
    https_proxy: # example: http_proxy: http://proxy.example.com:891
    webrtcturnserver:
        username: # example: username: myuser
        password: # example: password: mypassword
    ```

## Step 3: Deploy the application and Run multiple AI pipelines

Follow this procedure to run the sample application. In a typical deployment, multiple cameras deliver video streams that are connected to AI pipelines to improve the classification and recognition accuracy. The following demonstrates running multiple AI pipelines and visualization in the Grafana.

1. Deploy Helm chart

    ```sh
    helm install loitering-detection ./loitering-detection/helm-chart -n ld  --create-namespace
    ```

2. Verify all the pods and services are running:

    ```sh
    kubectl get pods -n ld
    kubectl get svc -n ld
    ```

3. Start the application with the Client URL (cURL) command by replacing the <HOST_IP> with the Node IP. (Total 8 places)

``` sh
curl -k https://<HOST_IP>:30443/api/pipelines/user_defined_pipelines/object_tracking_1 -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/VIRAT_S_000101.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_tracking_1",
            "publish_frame":false
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_tracking_1"
        }
    },
    "parameters": {
        "detection-device": "CPU"
    }
}'

curl -k https://<HOST_IP>:30443/api/pipelines/user_defined_pipelines/object_tracking_2 -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/VIRAT_S_000102.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_tracking_2",
            "publish_frame":false
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_tracking_2"
        }
    },
    "parameters": {
        "detection-device": "CPU"
    }
}'

curl -k https://<HOST_IP>:30443/api/pipelines/user_defined_pipelines/object_tracking_3 -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/VIRAT_S_000103.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_tracking_3",
            "publish_frame":false
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_tracking_3"
        }
    },
    "parameters": {
        "detection-device": "CPU"
    }
}'

curl -k https://<HOST_IP>:30443/api/pipelines/user_defined_pipelines/object_tracking_4 -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/VIRAT_S_000104.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_tracking_4",
            "publish_frame":false
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_tracking_4"
        }
    },
    "parameters": {
        "detection-device": "CPU"
    }
}'
```

4. View the Grafana and WebRTC streaming on `https://<HOST_IP>:30443/grafana/`.
    - Log in with the following credentials:
        - **Username:** `admin`
        - **Password:** `admin`
    - Check under the Dashboards section for the default dashboard named "Video Analytics Dashboard".

   ![Example of Grafana and WebRTC streaming](_images/grafana.png)

   Figure 1: Grafana and WebRTC streaming

## Step 4: End the demonstration

Follow this procedure to stop the sample application and end this demonstration.

1. Stop the sample application with the following command that uninstalls the release loitering-detection.

    ```sh
    helm uninstall loitering-detection -n ld
    ```


2. Confirm the pods are no longer running.

    ```sh
    kubectl get pods -n ld
    ```


## Summary

In this guide, you installed and validated Loitering Detection sample application. You also completed a demonstration where multiple pipelines run on a single system with near real-time classification.


## Troubleshooting

The following are options to help you resolve issues with the sample application.

### Deploying with Intel GPU K8S Extension on Intel® Tiber™ Edge Platform

If you're deploying a GPU based pipeline (example: with VA-API elements like `vapostproc`, `vah264dec` etc., and/or with `device=GPU` in `gvadetect` in `config.json`) with Intel GPU k8s Extension on Intel® Tiber™ Edge Platform, ensure to set the below details in the file `helm/values.yaml` appropriately in order to utilize the underlying GPU.
```sh
gpu:
  enabled: true
  type: "gpu.intel.com/i915"
  count: 1
```

### Deploying without Intel GPU K8S Extension

If you're deploying a GPU based pipeline (example: with VA-API elements like `vapostproc`, `vah264dec` etc., and/or with `device=GPU` in `gvadetect` in `config.json`) without Intel GPU k8s Extension, ensure to set the following details in the file `helm/values.yaml` appropriately in order to utilize the underlying GPU.
```sh
privileged_access_required: true
```

### Error Logs

View the container logs using the following command:

         kubectl logs -f <pod_name> -n ld