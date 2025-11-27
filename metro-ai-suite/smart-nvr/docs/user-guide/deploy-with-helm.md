# How to deploy with Helm\* Chart

This section shows how to deploy the Video Search and Summary Sample Application using Helm chart.

## Prerequisites
Before you begin, ensure that you have the following:
- Kubernetes\* cluster set up and running.
- The cluster must support **dynamic provisioning of Persistent Volumes (PV)**. Refer to the [Kubernetes Dynamic Provisioning Guide](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/) for more details.
- Install `kubectl` on your system. See the [Installation Guide](https://kubernetes.io/docs/tasks/tools/install-kubectl/). Ensure access to the Kubernetes cluster.
- Helm chart installed on your system. See the [Installation Guide](https://helm.sh/docs/intro/install/).
- **Storage Requirement :** Application requests for **50GiB** of storage in its default configuration. (This should change with choice of models and needs to be properly configured). Please make sure that required storage is available in you cluster.

Before setting up Smart NVR, ensure these services are running on their respective devices:

## 1. VSS (Video Search and Summarization) Services
Deploy these on separate devices:
- **VSS Search**: Handles video search functionality
- **VSS Summary**: Provides video summarization capabilities

📖 [VSS Documentation](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/sample-applications/video-search-and-summarization/docs/user-guide/get-started.md)

## 2. VLM Microservice (Optional)
Required only when enabling AI-powered event descriptions (`NVR_GENAI=true`):
- Runs the VLM model defined in the frigate [config file](../../resources/frigate-config/config.yml)
- Use `VLM_MAX_COMPLETION_TOKENS` to limit response length during deployment

📖 [VLM Serving Documentation](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/vlm-openvino-serving/docs/user-guide/get-started.md)


## Helm Chart Installation

In order to setup the end-to-end application, we need to acquire the charts and install it with optimal values and configurations. Subsequent sections will provide step by step details for the same.

### 1. Acquire the helm chart

There are 2 options to get the charts in your workspace:

#### Option 1: Get the charts from Docker Hub

##### Step 1: Pull the Specific Chart

Use the following command to pull the Helm chart from Docker Hub:
```bash
helm pull oci://registry-1.docker.io/intel/smart-nvr --version 1.2.1
```

Refer to the release notes for details on the latest version number to use for the sample application.

##### Step 2: Extract the `.tgz` File

After pulling the chart, extract the `.tgz` file:
```bash
tar -xvf smart-nvr-1.2.1.tgz
```

This will create a directory named `smart-nvr` containing the chart files. Navigate to the extracted directory to access the charts.

```bash
cd smart-nvr
```

#### Option 2: Install from Source

##### Step 1: Clone the Repository

Clone the repository containing the Helm chart:
```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
```

##### Step 2: Change to the Chart Directory

Navigate to the chart directory:

```bash
cd edge-ai-suites/metro-ai-suite/smart-nvr
```


### 2. Configure Required Values

The application requires several values to be set by user in order to work. To make it easier, we have included a `user_values_override.yaml` file, which contains only the values that user needs to tweak. Open the file in your favorite editor or use nano:

```bash
nano user_values_override.yaml
```

Update or edit the values in YAML file as follows:

| Key | Description | Example Value |
| --- | ----------- | ------------- |
| `global.pvcName` | Name for PVC to be used for storage by all components of application | `nvr-resource` |
| `global.keepPvc` | PVC gets deleted by default once helm is uninstalled. Set this to true to persist PVC (helps avoid delay due to model re-downloads when re-installing chart). | `true` or `false` |
| `global.proxy.http_proxy` | HTTP proxy if required | `http://proxy-example.com:000` |
| `global.proxy.https_proxy` | HTTPS proxy if required | `http://proxy-example.com:000` |
| `frigate.env.FRIGATE_MQTT_USER` | User name for mqtt | `<your-mqtt-username>` |
| `frigate.env.FRIGATE_MQTT_PASSWORD` | Password for mqtt | `<your-mqtt-password>` |
| `frigate.env.OPENAI_BASE_URL` | Needed when NVR_GENAI flag is set to true | `<your-open-ai-base-url>` |
| `frigate.env.OPENAI_API_KEY` | Needed when NVR_GENAI flag is set to true | `<your-open-ai-api-key>` |
| `nvr-event-router.env.VSS_SEARCH_IP` | VSS Search IP | `<your-vss-search-ip>` |
| `nvr-event-router.env.VSS_SEARCH_PORT` | VSS Search port | `<your-vss-search-port>` |
| `nvr-event-router.env.VSS_SUMMARY_IP` | VSS summary IP | `<your-vss-summary-ip>` |
| `nvr-event-router.env.VSS_SUMMARY_PORT` | VSS summary port | `<your-vss-summary-port>` |
| `nvr-event-router-ui.NVR_GENAI` | Flag to enable GENAI on Frigate NVR  | `true/false` |

### 3. Build Helm Dependencies

Navigate to the chart directory and build the Helm dependencies using the following command:

```bash
helm dependency build
```

### 4. Set and Create a Namespace

We will install the helm chart in a new namespace. Create a shell variable to refer a new namespace and create it.

1. Refer a new namespace using shell variable `my_namespace`. Set any desired unique value.

    ```bash
    my_namespace=foobar
    ```

2. Create the Kubernetes namespace. If it is already created, creation will fail. You can update the namespace in previous step and try again.

    ```bash
    kubectl create namespace $my_namespace
    ```

> **_NOTE :_** All subsequent steps assume that you have `my_namespace` variable set and accessible on your shell with the desired namespace as its value.


### 5. Deploy the Helm Chart


Deploy the Smart NVR Application:

```bash
helm install smart-nvr . -f user_value_override.yaml -n $my_namespace
```

### Step 6: Verify the Deployment

Check the status of the deployed resources to ensure everything is running correctly:

```bash
kubectl get pods -n $my_namespace
```

**Before proceeding to access the application we must ensure the following status of output of the above command:**

1. Ensure all pods are in the "Running" state. This is denoted by **Running** state mentioned in the **STATUS** column.

2. Ensure all containers in each pod are _Ready_. As all pods are running single container only, this is typically denoted by mentioning **1/1** in the **READY** column.

> **_IMPORTANT NOTE :_** When deployed for first time, it may take up-to around 5 Mins to bring all the pods/containers in running and ready state, as several containers try to download models which can take a while. The time to bring up all the pods depends on several factors including but not limited to node availability, node load average, network speed, compute availability etc.

> **_IMPORTANT NOTE :_** If you want to persist the downloaded models and avoid delays pertaining to model downloads when re-installing the charts, please set the `global.keepPvc` value to `true` in `user_values_override.yaml` file before installing the chart.

### Step 7: Accessing the application

Nginx service running as a reverse proxy in one of the pods, helps us to access the application. We need to get Host IP and Port on the node where the nginx service is running.

Run the following command to get the host IP of the node and port exposed by Nginx service:

```bash
smart_nvr_ip=$(kubectl get pods -l app=nvr-event-router-ui-nginx -n $my_namespace -o jsonpath='{.items[0].status.hostIP}')
smart_nvr_port=$(kubectl get service nvr-event-router-ui-nginx -n $my_namespace -o jsonpath='{.spec.ports[0].nodePort}')
echo "http://${smart_nvr_ip}:${smart_nvr_port}"
```

Copy the output of above bash snippet and paste it into your browser to access the **Video Search and Summarization Application**.

### Step 8: Update Helm Dependencies

If any changes are made to the sub-charts, always remember to update the Helm dependencies using the following command before re-installing or upgrading your helm installation:

```bash
helm dependency update
```

### Step 9: Uninstall Helm chart

To uninstall the Video Summary Helm chart, use the following command:

```bash
helm uninstall smart-nvr -n $my_namespace
```

## Verification

- Ensure that all pods are running and the services are accessible.
- Access the Video Summary application dashboard and verify that it is functioning as expected.
- Upload a test video to verify that the ingestion, processing, and summary pipeline works correctly.
- Check that all components (MinIO, PostgreSQL, RabbitMQ, video ingestion, VLM inference, audio analyzer) are functioning properly.

## Troubleshooting

- **Pods not coming in Ready or Running state for a long time.**

  There could be several possible reasons for this. Most likely reasons are storage unavailability, node unavailability, network slow-down or faulty network etc. Please check with your cluster admin or try fresh installation of charts, **after deleting the PVC _(see next issue)_ and un-installing the current chart**.

- **All containers Ready, all Pods in Running state, application UI is accessible but search or summary is failing.**

  - Verify that the VSS Search and Summary services are running properly.
  - If PVC has been configured to be retained, most common reason for application to fail to work is a stale PVC. This problem most likely occurs when helm charts are re-installed after some updates to helm chart or the application image. To fix this, delete the PVC before re-installing the helm chart by following command:

    ```bash
    kubectl delete pvc nvr-resource -n <your_namespace>
    ```

  If you have updated the `global.pvcName` in the values file, use the updated name instead of default PVC name `nvr-resource` in above command.

- If you encounter any issues during the deployment process, check the Kubernetes logs for errors:

    ```bash
    kubectl logs <pod-name> -n $my_namespace
    ```

- Some issues might be fixed by freshly setting up storage. This is helpful in cases where deletion of PVC is prohibited by configuration on charts un-installation (when `global.keepPvc` is set to true):

    ```bash
    kubectl delete pvc <pvc-name> -n $my_namespace
    ```
## Related links
- [How to Build from Source](./how-to-build-from-source.md)