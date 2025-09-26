# Deploy with Helm

Use Helm to deploy Image-Based Video Search to a Kubernetes cluster. This guide
will help you:

- Add the Helm chart repository.
- Configure the Helm chart to match your deployment needs.
- Deploy and verify the application.

Helm simplifies Kubernetes deployments by streamlining configurations and
enabling easy scaling and updates. For more details, see
[Helm Documentation](https://helm.sh/docs/).

## Prerequisites

Before You Begin, ensure the following:

- **System Requirements**: Verify that your system meets the
  [minimum requirements](./system-requirements.md).
- **Tools Installed**: Install the required tools:
  - Kubernetes CLI (kubectl)
  - Helm 3 or later

## Pull the helm chart (Optional)

- Note: The helm chart should be downloaded when you are not using the helm chart provided in `edge-ai-suites/metro-ai-suite/image-based-video-search/chart`

- Download helm chart with the following command

    `helm pull oci://registry-1.docker.io/intel/image-based-video-search --version 1.0.2-pre-RC1`
- unzip the package using the following command

    `tar -xvf image-based-video-search-1.0.2-pre-RC1.tgz`
- Get into the helm directory

    `cd image-based-video-search`

## Steps to Deploy

Clone the repo and go to helm directory
```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites/metro-ai-suite/image-based-video-search/chart
```

```bash
# Install the Image-Based Video Search chart in the ibvs namespace
helm install ibvs . --create-namespace -n ibvs 
```

Some containers in the deployment requires network access. If you are in a proxy
environment, pass the proxy environment variables as follows:

```bash
# Install the Image-Based Video Search chart in the ibvs namespace
# Replace the proxy values with the specific ones for your environment:
helm install ibvs . --create-namespace -n ibvs \
    --set httpProxy="http://proxy.example.com:8080" \
    --set httpsProxy="http://proxy.example.com:8080" \
    --set noProxy="localhost\,127.0.0.1"
```

To get the port where the application is serving, run the following command:

```bash
kubectl -n ibvs get svc/ibvs-app
```

This is an example output of the previous command:

```text
NAME       TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
ibvs-app   NodePort   10.109.118.49   <none>        3000:31998/TCP   14m
```

Now frontend should be accessible at http://localhost:31998/.
> Note: To access the above url remotely, replace the `localhost` with your system IP address. 

Finally, the app can be uninstalled using the following command:

```bash
# And this is how you uninstall the chart:
helm uninstall -n ibvs ibvs
```

## Troubleshooting

1. **Helm Chart Not Found**:

   - Check if the Helm repository was added:

     ```bash
     helm repo list
     ```

1. **Pods Not Running**:

   - Review pod logs:

     ```bash
     kubectl logs {{pod-name}} -n {{namespace}}
     ```

1. **Service Unreachable**:

   - Confirm the service configuration:

     ```bash
     kubectl get svc -n {{namespace}}
     ```

## Supporting Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/home/)
- [Helm Documentation](https://helm.sh/docs/)
