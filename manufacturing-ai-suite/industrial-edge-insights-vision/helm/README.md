# Helm based deployment 

General instructions for helm based deployment is as follows. This assumes you have the Kubernetes cluster already setup and running.

1. Prepare `values.yaml` file to configure the helm chart for your application
2. Run `./setup.sh helm` to set env file for scripts to source and identify application specific data such as `HOST_IP`, `REST_SERVER_PORT` and `SAMPLE_APP` directory.
3. Install the helm chart to deploy the app to Kubernetes
4. Copy the resources to container volumes. This is done so that deployments such as ITEP can run where volumes mounts are not feasible.
5. Run `sample_start.sh` to start pipeline. This sends curl request with pre-defined payload to the running DLStreamer Pipeline Server.
6. Run `sample_status.sh` or `sample_list.sh` to monitor pipeline status or list available pipelines.
7. Run `sample_stop.sh` to abort any running pipeline(s).
8. Uninstall the helm chart.

Using the template above, several industrial recipies have been provided for users to deploy using helm on k8s cluster. Click on the applications below to get started.

* [Pallet Defect Detection](apps/pallet-defect-detection/README.md)
* [Weld Porosity Classfication](apps/weld-porosity/README.md)
