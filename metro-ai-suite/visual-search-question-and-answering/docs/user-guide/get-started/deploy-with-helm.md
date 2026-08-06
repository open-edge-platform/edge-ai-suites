# Deploy with Helm

This section shows how to deploy the Visual Search and QA Application using Helm chart.

## Prerequisites

Before you begin, ensure that you have the following:

- Kubernetes\* cluster set up and running.
- The cluster must support **dynamic provisioning of Persistent Volumes (PV)**. Refer to the [Kubernetes Dynamic Provisioning Guide](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/) for more details.
- Install `kubectl` on your system. See the [Installation Guide](https://kubernetes.io/docs/tasks/tools/install-kubectl/). Ensure access to the Kubernetes cluster.
- Helm chart installed on your system. See the [Installation Guide](https://helm.sh/docs/intro/install/).

## Steps to deploy with Helm

Do the following to deploy VSQA using Helm chart.

### Step 1: Acquire the helm chart

#### Option 1: Get the charts from Docker Hub

Use the following command to pull the Helm chart from Docker Hub:

```bash
helm pull oci://registry-1.docker.io/intel/metro-ai-suite-vsqa-chart
```

You may add `--version <version-no>` to specify a version number. Refer to the release notes for details on the latest version number to use for the sample application.

After pulling the chart, extract the `.tgz` file

```bash
tar -xvf metro-ai-suite-vsqa-chart-<version-no>.tgz
```

This will create a directory named `metro-ai-suite-vsqa-chart` containing the chart files. Navigate to the extracted directory with to access the charts.

```bash
cd metro-ai-suite-vsqa-chart
```

#### Option 2: Install from source

Clone the source repository

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git -b main
```

Navigate to the chart directory

```bash
cd edge-ai-suites/metro-ai-suite/visual-search-question-and-answering/deployment/helm-chart
```

### Step 2: Configure the `values.yaml` File

Edit the `values.yaml` file to set the necessary environment variables. At minimum, ensure you set the models, and proxy settings as required.

#### Settings that must be configured

| Key | Description | Example Value |
| --- | ----------- | ------------- |
| `global.proxy.http_proxy` | HTTP proxy if required | `http://proxy-example.com:000` |
| `global.proxy.https_proxy` | HTTPS proxy if required | `http://proxy-example.com:000` |
| `global.VLM_MODEL_NAME` | VLM model to be used by vlm-openvino-serving | `Qwen/Qwen2.5-VL-7B-Instruct` |
| `global.EMBEDDING_MODEL_NAME` | Embedding model to be used for feature extraction by multimodal-embedding-serving  | `CLIP/clip-vit-h-14` |
| `global.registry` | Remote registry to pull images from. Default as blank | `intel/` |
| `global.env.keeppvc` | Set to true to persist the storage. Default is false | false |
| `MILVUS_HOST` | Milvus service address. Change this if Milvus is not installed in the `milvus` namespace | `my-milvus.milvus.svc.cluster.local` |

The chart is namespace-agnostic: in-cluster service URLs are derived from the
release namespace, so it can be installed into any namespace.

#### Selecting the inference device

Each service picks its own device. `CPU` works everywhere and is the default.

| Key | Description | Example Value |
| --- | ----------- | ------------- |
| `vlmOpenvinoServing.env.VLM_DEVICE` | Device for the VLM | `CPU`, `GPU` |
| `multimodalembeddingServing.env.EMBEDDING_DEVICE` | Device for query embedding | `CPU`, `GPU`, `NPU` |
| `multimodalDataprep.env.MM_DATAPREP_EMBEDDING_DEVICE` | Device for ingest embedding | `CPU`, `GPU`, `NPU` |
| `multimodalDataprep.env.MM_DATAPREP_DETECTION_DEVICE` | Device for object detection | `CPU`, `GPU`, `NPU` |

When a service is set to `GPU` or `NPU` you must also request the matching
device-plugin resource for it, otherwise OpenVINO fails at startup with
`[GPU] Can't get PERFORMANCE_HINT property as no supported devices found`.
This requires the [Intel Device Plugins for
Kubernetes](https://github.com/intel/intel-device-plugins-for-kubernetes) to be
installed on the cluster:

```yaml
multimodalembeddingServing:
  resources:
    limits:
      gpu.intel.com/i915: 1   # or npu.intel.com/accel: 1 for NPU
```

The same `resources` key is available on `vlmOpenvinoServing` and
`multimodalDataprep`.

The container user must also belong to the groups owning the device nodes.
Check the group ids on the target node and set them accordingly, as they differ
between hosts:

```bash
ls -ln /dev/dri     # 3rd column is the gid: card* -> videoGroupId, renderD* -> renderGroupId
```

```yaml
multimodalembeddingServing:
  videoGroupId: 44
  renderGroupId: 110   # frequently 992 or 993 on newer distributions
```

#### Pinning the pods to a node

`volumes.hostDataPath` is a host path and the accelerator device nodes are
node-local, so on a multi-node cluster the pods must land on the node that
actually holds the data and the devices:

```yaml
global:
  nodeSelector:
    kubernetes.io/hostname: <node-name>
```

#### Optional settings

| Key | Description | Default |
| --- | ----------- | ------- |
| `multimodalDataprep.env.MM_DATAPREP_ENABLE_OBJECT_DETECTION` | Also embed detected object crops in addition to full frames | `"false"` |
| `visualSearchQaApp.env.DATA_INGEST_WITH_DETECT` | App-side request for the above. Keep both in sync | `false` |
| `visualSearchQaApp.env.DATAPREP_PUBLIC_BASE_URL` | Browser-reachable dataprep address used to stream search results. Leave blank when the browser can reach the cluster service directly | `""` |
| `*.env.HF_ENDPOINT` | Hugging Face mirror used to download models. Set to `https://huggingface.co` outside mainland China | `https://hf-mirror.com` |

### Step 3: Build Helm Dependencies

Navigate to the chart directory and build the Helm dependencies using the following command:

```bash
helm dependency update
```

### Step 4: Deploy Milvus as the vector DB

Create a namespace for Milvus

```bash
kubectl create namespace milvus
```

Install Milvus latest helm chart

```bash
helm repo add milvus https://zilliztech.github.io/milvus-helm/
helm repo update
```

Deploy Milvus in a simplified standalone mode

```bash
helm install my-milvus milvus/milvus -n milvus --set image.all.tag=v2.6.0   --set cluster.enabled=false --set etcd.replicaCount=1 --set minio.mode=standalone --set pulsar.enabled=false --set pulsarv3.enabled=false
```

**Note**: if you need customized settings for Milvus, please refer to [the official guide](https://milvus.io/docs/v2.5.x/install_cluster-helm.md).

Check the pods status with `kubectl get po -n milvus`. `RESTARTS` are possible, as long as the 3 pods are stablized after a while, the deployment is successful.

### Step 5: Prepare host directories for models and data

```sh
mkdir -p $HOME/data
```

Make sure the host directories are available to the cluster nodes, and the host-paths under the `volumes.hostDataPath` section in `values.yaml` file match the correct directories. Particularly, the default path in `values.yaml` is `/home/user/data`, which corresponds to a host username `user`.

This directory is mounted from the node, not from your workstation, so the media
to be ingested must be placed on the node the pods are scheduled on (see
`global.nodeSelector` above).

Note: supported media types: jpg, png, mp4

### Step 6: Deploy the Application

Create a namespace for VSQA app

```bash
kubectl create namespace vsqa
```

Install

```bash
helm install vsqa . --values values.yaml -n vsqa
```

### Step 7: Verify the Deployment

Check the status of the deployed resources to ensure everything is running correctly:

```bash
kubectl get pods -n vsqa
kubectl get services -n vsqa
```

Ensure all pods are in the "Running" state before proceeding.

### Step 8: Access the application

For a simpler access, we can do a port forward

```bash
kubectl port-forward -n vsqa svc/visual-search-qa-app 17580:17580
```

Leave the session alive, then access `http://localhost:17580` to view the application.

### Step 9: Uninstall the Application

To uninstall, use the following command:

```bash
helm uninstall vsqa -n vsqa
helm uninstall my-milvus -n milvus
```

## Verification

- Ensure that all pods are running and the services are accessible.

## Troubleshooting

- If you encounter any issues during the deployment process, check the Kubernetes logs for errors:

  ```bash
  kubectl logs <pod-name> -n <your-namespace>
  ```

- If the data preparation pod shows error while loading a large dataset, it might be caused by too large of the dataset size. Try breaking the dataset into smaller subsets and ingest each of them instead.

- If a pod using a GPU or NPU crash-loops with `[GPU] Can't get PERFORMANCE_HINT
  property as no supported devices found`, the container can see the device node
  but cannot use it. Check that the device-plugin resource is requested under
  that service's `resources.limits`, and that `renderGroupId`/`videoGroupId`
  match the gids reported by `ls -ln /dev/dri` on the node.

- If requests between the services time out with `504 Gateway Timeout`, the
  in-cluster traffic is being sent through an HTTP proxy. Add
  `.svc.cluster.local` to `global.proxy.no_proxy`.

## Related links

- [Get started with docker-compose](../get-started.md)