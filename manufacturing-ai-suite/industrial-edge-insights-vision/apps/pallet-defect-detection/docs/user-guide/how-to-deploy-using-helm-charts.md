# Deploy using Helm charts

## Prerequisites

- [System Requirements](system-requirements.md)
- K8s installation on single or multi node must be done as pre-requisite to continue the following deployment. Note: The kubernetes cluster is set up with `kubeadm`, `kubectl` and `kubelet` packages on single and multi nodes with `v1.30.2`.
  Refer to tutorials online to setup kubernetes cluster on the web with host OS as ubuntu 22.04 and/or ubuntu 24.04.
- For helm installation, refer to [helm website](https://helm.sh/docs/intro/install/)


## Setup the application

> **Note**: The following instructions assume Kubernetes is already running in the host system with helm package manager installed.

1. Clone the **edge-ai-suites** repository and change into industrial-edge-insights-vision directory. The directory contains the utility scripts required in the instructions that follows.
    ```sh
    git clone https://github.com/open-edge-platform/edge-ai-suites.git
    cd manufacturing-ai-suite/industrial-edge-insights-vision
    ```
2. Set app specific values.yaml file.
    ```sh
    cp helm/values_pallet_defect_detection.yaml helm/values.yaml
    ```
3.  Edit the HOST_IP, proxy and other environment variables in `helm/values.yaml` as follows
    ```yaml
    env:        
        HOST_IP: <HOST_IP>   # host IP address
        http_proxy: <http proxy> # proxy details if behind proxy
        https_proxy: <https proxy>
        SAMPLE_APP: pallet-defect-detection # application directory
    webrtcturnserver:
        username: <username>  # WebRTC credentials e.g. intel1234
        password: <password>
    ```
4.  Install pre-requisites. Run with sudo if needed.
    ```sh
    ./setup.sh helm
    ```
    This sets up application pre-requisites, download artifacts, sets executable permissions for scripts etc. Downloaded resource directories.

## Deploy the application

5.  Install the helm chart
    ```sh
    helm install app-deploy helm -n apps --create-namespace
    ```
    After installation, check the status of the running pods:
    ```sh
    kubectl get pods -n apps
    ```
    To view logs of a specific pod, replace `<pod_name>` with the actual pod name from the output above:
    ```sh
    kubectl logs -n apps -f <pod_name>
    ```

6.  Copy the resources such as video and model from local directory to the to the `dlstreamer-pipeline-server` pod to make them available for application while launching pipelines.
    ```sh
    # Below is an example for Pallet Defect Detection. Please adjust the source path of models and videos appropriately for other sample applications.
    
    POD_NAME=$(kubectl get pods -n apps -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

    kubectl cp resources/pallet-defect-detection/videos/warehouse.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n apps

    kubectl cp resources/pallet-defect-detection/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n apps
    ```
7.  Fetch the list of pipeline loaded available to launch
    ```sh
    ./sample_list.sh
    ```
    This lists the pipeline loaded in DLStreamer Pipeline Server.
    
    Output:
    ```sh
    # Example output for Pallet Defect Detection
    Environment variables loaded from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pallet-defect-detection
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Loaded pipelines:
    [
        ...
        {
            "description": "DL Streamer Pipeline Server pipeline",
            "name": "user_defined_pipelines",
            "parameters": {
            "properties": {
                "detection-properties": {
                "element": {
                    "format": "element-properties",
                    "name": "detection"
                }
                }
            },
            "type": "object"
            },
            "type": "GStreamer",
            "version": "pallet_defect_detection"
        }
        ...
    ]
    ```
8.  Start the sample application with a pipeline.
    ```sh
    ./sample_start.sh -p pallet_defect_detection
    ```
    This command would look for the payload for the pipeline specified in `-p` argument above, inside the `payload.json` file and launch the a pipeline instance in DLStreamer Pipeline Server. Refer to the table, to learn about different options available. 
    
    Output:
    ```sh
    # Example output for Pallet Defect Detection
    Environment variables loaded from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pallet-defect-detection
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Loading payload from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/apps/pallet-defect-detection/payload.json
    Payload loaded successfully.
    Starting pipeline: pallet_defect_detection
    Launching pipeline: pallet_defect_detection
    Extracting payload for pipeline: pallet_defect_detection
    Found 1 payload(s) for pipeline: pallet_defect_detection
    Payload for pipeline 'pallet_defect_detection' {"source":{"uri":"file:///home/pipeline-server/resources/videos/warehouse.avi","type":"uri"},"destination":{"frame":{"type":"webrtc","peer-id":"pdd"}},"parameters":{"detection-properties":{"model":"/home/pipeline-server/resources/models/models/pallet-defect-detection/model.xml","device":"CPU"}}}
    Posting payload to REST server at http://<HOST_IP>:30107/pipelines/user_defined_pipelines/pallet_defect_detection
    Payload for pipeline 'pallet_defect_detection' posted successfully. Response: "99ac50d852b511f09f7c2242868ff651"
    ```
    >NOTE- This would start the pipeline. You can view the inference stream on WebRTC by opening a browser and navigating to http://<HOST_IP>:31111/pdd/ for Pallet Defect Detection.

9.  Get status of pipeline instance(s) running.
    ```sh
    ./sample_status.sh
    ```
    This command lists status of pipeline instances launched during the lifetime of sample application.
    
    Output:
    ```sh
    # Example output for Pallet Defect Detection
    Environment variables loaded from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pallet-defect-detection
    [
    {
        "avg_fps": 30.00446179356829,
        "elapsed_time": 36.927825689315796,
        "id": "99ac50d852b511f09f7c2242868ff651",
        "message": "",
        "start_time": 1750956469.620569,
        "state": "RUNNING"
    }
    ]
    ```

10. Stop pipeline instance.
    ```sh
    ./sample_stop.sh
    ```
    This command will stop all instances that are currently in `RUNNING` state and respond with the last status.
    
    Output:
    ```sh
    # Example output for Pallet Defect Detection
    No pipelines specified. Stopping all pipeline instances
    Environment variables loaded from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pallet-defect-detection
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Instance list fetched successfully. HTTP Status Code: 200
    Found 1 running pipeline instances.
    Stopping pipeline instance with ID: 99ac50d852b511f09f7c2242868ff651
    Pipeline instance with ID '99ac50d852b511f09f7c2242868ff651' stopped successfully. Response: {
    "avg_fps": 30.01631239459745,
    "elapsed_time": 49.30651903152466,
    "id": "99ac50d852b511f09f7c2242868ff651",
    "message": "",
    "start_time": 1750960037.1471195,
    "state": "RUNNING"
    }
    ```
    If you wish to stop a specific instance, you can provide it with an `--id` argument to the command.    
    For example, `./sample_stop.sh --id 99ac50d852b511f09f7c2242868ff651`

11. Uninstall the helm chart.
     ```sh
     helm uninstall app-deploy -n apps
     ```


## Troubleshooting
- [Troubleshooting Guide](troubleshooting-guide.md)