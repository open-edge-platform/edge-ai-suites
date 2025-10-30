# How to deploy with Helm Chart

This section shows how to deploy the Visual Search and QA Application using Helm chart.

## Prerequisites
Before you begin, ensure that you have the following:
- Kubernetes\* cluster set up and running.
- The cluster must support **dynamic provisioning of Persistent Volumes (PV)**. Refer to the [Kubernetes Dynamic Provisioning Guide](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/) for more details.
- Install `kubectl` on your system. See the [Installation Guide](https://kubernetes.io/docs/tasks/tools/install-kubectl/). Ensure access to the Kubernetes cluster. 
- Helm chart installed on your system. See the [Installation Guide](https://helm.sh/docs/intro/install/).
- PVC storage class is required to support `RWMany` mode. In case the default storage class used does not support it, consider using storage solution like [LongHorn](https://longhorn.io/docs/) that provides this support.


## Steps to deploy with Helm
Do the following to deploy VSQA using Helm chart. 

### Step 1: Clone the Repository

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git -b release-1.2.0
```

#### Step 2: Change to the Chart Directory

```bash
cd edge-ai-suites/metro-ai-suite/visual-search-question-and-answering/deployment/helm-chart
```

#### Step 3: Configure the `values.yaml` File

Edit the `values.yaml` file to set the necessary environment variables. At minimum, ensure you set the models, and proxy settings as required. Supported models can be found below:

##### Supported Local Embedding Models

| Model Name                          | Search in English | Search in Chinese | Remarks|
|-------------------------------------|----------------------|---------------------|---------------|
| CLIP-ViT-H-14                        | Yes                  | No                 |            |
| CN-CLIP-ViT-H-14              | Yes                  | Yes                  | Supports search text query in Chinese       | 

When prompting `Please enter the VLM_MODEL_NAME`, choose one model name from table below and input

##### Supported VLM Models

| Model Name                          | Single Image Support | Multi-Image Support | Video Support | Hardware Support                |
|-------------------------------------|----------------------|---------------------|---------------|---------------------------------|
| Qwen/Qwen2.5-VL-7B-Instruct         | Yes                  | Yes                 | Yes           | GPU                       |

##### Settings to be configured
| Key | Description | Example Value |
| --- | ----------- | ------------- |
| `global.proxy.http_proxy` | HTTP proxy if required | `http://proxy-example.com:000` |
| `global.proxy.https_proxy` | HTTPS proxy if required | `http://proxy-example.com:000` |
| `global.VLM_MODEL_NAME` | VLM model to be used by VLM Inference Microservice | `Qwen/Qwen2.5-VL-7B-Instruct` |
| `global.LOCAL_EMBED_MODEL_ID` | Local embedding model to be used for feature extraction | `CLIP-ViT-H-14` |
| `global.env.keeppvc` | Set true to persists the storage. Default is false | false |


### Step 4: Build Helm Dependencies

Navigate to the chart directory and build the Helm dependencies using the following command:

```bash
helm dependency build
```

### Step 5: Deploy Milvus as the vector DB

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

Note: if you need customized settings for Milvus, please refer to [the official guide](https://milvus.io/docs/v2.5.x/install_cluster-helm.md).

There should be these 3 pods under namesspace `milvus` after the deployment:
```
NAME                                    READY   STATUS    RESTARTS       AGE
my-milvus-etcd-0                        1/1     Running   1 (3d ago)     3d
my-milvus-minio-<some-id>               1/1     Running   0              3d
my-milvus-standalone-<some-id>          1/1     Running   14 (12h ago)   3d
```
Note that RESTARTS are possible, as long as the 3 pods are stablized after a while, the deployment is successful.


### Step 6: Deploy [intel-device-plugins-for-kubernetes](https://github.com/intel/intel-device-plugins-for-kubernetes)

Follw these steps to install with NFD

```bash
kubectl apply -k 'https://github.com/intel/intel-device-plugins-for-kubernetes/deployments/nfd?ref=v0.32.0'

kubectl apply -k 'https://github.com/intel/intel-device-plugins-for-kubernetes/deployments/nfd/overlays/node-feature-rules?ref=v0.32.0'

kubectl apply -k 'https://github.com/intel/intel-device-plugins-for-kubernetes/deployments/gpu_plugin/overlays/nfd_labeled_nodes?ref=v0.32.0'
```

### Step 7: Prepare host directories for models and data

```
mkdir -p $HOME/.cache/huggingface
mkdir -p $HOME/models
mkdir -p $HOME/data
```

Make sure all these host directories are available to the cluster, and the host-paths under the `volumes` section in the `values.yaml` file match the correct directories.

Note: supported media types: jpg, png, mp4

### Step 8: Deploy the Application

Create a namespace for VSQA app

```bash
kubectl create namespace vsqa
``` 

Install 

```bash
helm install vsqa . --values values.yaml -n vsqa
``` 


### Step 9: Verify the Deployment

Check the status of the deployed resources to ensure everything is running correctly:

```bash
kubectl get pods -n vsqa
kubectl get services -n vsqa
```

Ensure all pods are in the "Running" state before proceeding.

### Step 10: (Example) Try with a demo dataset

Find the dataprep pod which is under namespace `vsqa` and starts with `vsqa-dataprep-visualdata-milvus-`. Enter the pod

```bash
kubectl exec -ti -n vsqa <dataprep-pod-name> -- bash
```

Inside the pod container, run

```bash
python example/example_utils.py -d DAVIS
```

This script is for demo dataset preparation. After execution, some images and videos for demo are stored on host in `$HOME/data/DAVIS/subset` (may vary according to your host data directories setting in step 7 and `values.yaml`), use this path to do the next step.

Exit the pod. Go to `http://{host_ip}:17580` with a browser. Put the exact path to the subset of demo dataset (usually`/home/user/data/DAVIS/subset`, may vary according to your local username) into `file directory on host`. Click `UpdataDB`. Wait for a while and click `showInfo`. You should see that the number of processed files is 25.

Try searching with prompt `tractor`, see if the results are correct.

Expected valid inputs are "car-race", "deer", "guitar-violin", "gym", "helicopter", "carousel", "monkeys-trees", "golf", "rollercoaster", "horsejump-stick", "planes-crossing", "tractor"

Try ticking a search result, and ask a question in the leftside chatbox about the selected media.

Note: for each chat request, you may select either a single image, or multiple images, or a single video. Multiple videos or a collection of images+videos are not supported yet.


### Step 11: Uninstall the Application

To uninstall, use the following command:

```bash
helm uninstall vsqa -n vsqa
```

## Verification

- Ensure that all pods are running and the services are accessible.

## Troubleshooting

- If you encounter any issues during the deployment process, check the Kubernetes logs for errors:
  ```bash
  kubectl logs <pod-name> -n <your-namespace>
  ```

## Related links
- [Get started with docker-compose](./get-started.md)