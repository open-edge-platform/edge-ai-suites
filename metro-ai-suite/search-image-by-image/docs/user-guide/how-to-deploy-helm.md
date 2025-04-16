# Deploy with Helm

Use Helm to deploy Image-Based Video Search to a Kubernetes cluster. This guide will help you:
- Add the Helm chart repository.
- Configure the Helm chart to match your deployment needs.
- Deploy and verify the application.

Helm simplifies Kubernetes deployments by streamlining configurations and enabling easy scaling and updates. For more details, see [Helm Documentation](https://helm.sh/docs/).


## Prerequisites

Before You Begin, ensure the following:

- **System Requirements**: Verify that your system meets the [minimum requirements](./system-requirements.md).
- **Tools Installed**: Install the required tools:
    - Kubernetes CLI (kubectl)
    - Helm 3 or later

## Steps to Deploy

```bash
helm upgrade \
    --install sibi oci://registry-1.docker.io/intel/search-image-by-image \
    --create-namespace \
    -n sibi
```

Some containers in the deployment requires network access.
If you are in a proxy environment, pass the proxy environment variables as follows:

```bash
# Install the Image-Based Video Search chart in the sibi namespace
# Replace the proxy values with the specific ones for your environment:
helm upgrade \
    --install sibi oci://registry-1.docker.io/intel/search-image-by-image \
    --create-namespace \
    --set httpProxy="http://proxy.example.com:8080" \
    --set httpsProxy="http://proxy.example.com:8080" \
    --set noProxy="localhost\,127.0.0.1" \
    -n sibi
```

To get the port where the application is serving, run the following command:

```bash
kubectl -n sibi get svc/sibi-app
```

This is an example output of the previous command:

```text
NAME       TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
sibi-app   NodePort   10.109.118.49   <none>        3000:31998/TCP   14m
```

Now frontend should be accessible at http://localhost:31998/.

Finally, the app can be uninstalled using the following command:

```bash
# And this is how you uninstall the chart:
helm uninstall -n sibi sibi
```

## Troubleshooting

1. **Helm Chart Not Found**:

   - Check if the Helm repository was added:

     ```bash
     helm repo list
     ```

2. **Pods Not Running**:

   - Review pod logs:

     ```bash
     kubectl logs {{pod-name}} -n {{namespace}}
     ```

3. **Service Unreachable**:

   - Confirm the service configuration:

     ```bash
     kubectl get svc -n {{namespace}}
     ```


## Supporting Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/home/)
- [Helm Documentation](https://helm.sh/docs/)
