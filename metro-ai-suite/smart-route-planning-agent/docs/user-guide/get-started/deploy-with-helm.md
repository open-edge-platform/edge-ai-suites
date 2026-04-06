# How to Deploy with Helm

This guide explains a simple Helm deployment for Smart Route Planning Agent.

## Prerequisites

- A Kubernetes cluster and kubectl access with required permissions to create PVC and namespaces.
- Helm installed.
- At least **2 instances of  Smart Traffic Intersection Agent** should be running and reachable. This is required for route planning to work correctly. (If no such instances are available, application can still be deployed and accessed by following this guide. However, no route planning will be done.)
- Use this guide to deploy Smart Traffic Intersection Agent with Helm:
  [Smart Traffic Intersection Agent - Deploy with Helm](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/smart-traffic-intersection-agent/docs/user-guide/get-started/deploy-with-helm.md)

## Helm Version

- Validated with **Helm v3.15.x**.
- Recommended: **Helm v3.13+**.

## Installing the Chart

### Step 1: Get the Chart (Choose One Option)

#### Option A: From Source Code

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites/metro-ai-suite/smart-route-planning-agent/chart
```

#### Option B: From Public Registry

Follow these 2 simple steps:

1. Set the version of the helm chart required. Check different versions available here: https://hub.docker.com/r/intel/smart-route-planning-agent

    ```bash
    helm_version=<version>
    ```

2. Pull the helm chart and extract its content:

    ```bash
    helm pull oci://registry-1.docker.io/intel/smart-route-planning-agent --version ${helm_version}
    tar -xvf smart-route-planning-agent-${helm_version}.tgz
    cd smart-route-planning-agent
    ```

### Step 2: Override the Default Values

Before installing, edit `values_override.yaml` file in the current directory.

```bash
nano values_override.yaml
```

Set the required values:

- `trafficIntersections.hosts`: add 2 or more Smart Traffic Intersection Agent endpoints.
- `httpProxy`, `httpsProxy`, `noProxy`: set these only if you are behind a proxy.

Important proxy note:

- If Smart-Traffic-Intersection-Agent instances are on the same private network, add their IPs to `noProxy`.
- Private subnets are already included by default in `values_override.yaml`, but better add explicit IPs when needed.

Example:

```yaml
httpProxy: "http://proxy.example.com:916"
httpsProxy: "http://proxy.example.com:916"
noProxy: "localhost,127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,10.1.2.3,10.1.2.4"

trafficIntersections:
  apiEndpoint: "/api/v1/traffic/current?images=false"
  hosts:
    - "http://10.1.2.3:8081"
    - "http://10.1.2.4:8081"
```

### Step 3: Set a Namespace Variable

Set it to a namespace you want to use (even if it is already created).

```bash
namespace=<namespace_name>
```

### Step 4: Install the Chart

```bash
helm upgrade --install srpa . -n ${namespace} --create-namespace -f values_override.yaml
```

> __**Note:**__ If you do not have permission to create a namespace and your cluster admin has already provided a namespace, use the following command instead: `helm upgrade --install srpa . -n ${namespace} -f values_override.yaml`. (Make sure you have already set the namespace veriable to required value in step 3.)


### Step 5: Wait for Ready Pods

```bash
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=srpa -n ${namespace} --timeout=300s
```

### Step 6: Access the Application

To access the application, get the IP of the node where the pod is running and the port which is exposed:

```bash
NODE_NAME=$(kubectl get pod -n ${namespace} -l app.kubernetes.io/instance=srpa -o jsonpath='{.items[0].spec.nodeName}')
NODE_IP=$(kubectl get node "$NODE_NAME" -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}')
NODE_PORT=$(kubectl get svc -n ${namespace} -l app.kubernetes.io/instance=srpa,app.kubernetes.io/name=smart-route-planning-agent -o jsonpath='{.items[0].spec.ports[0].nodePort}')
echo "http://${NODE_IP}:${NODE_PORT}"
```

The above command will give the complete URL for the application in your terminal. Access the URL in a web browser to use the application.

## Uninstall the Chart

By uninstalling the chart, you can remove the Smart Route Planning Agent application and its resource from the cluster.

```bash
helm uninstall srpa -n ${namespace}
```

You can verify whether all resources are removed or not, using following command:

```bash
kubectl get all -n ${namespace} | grep srpa
```
