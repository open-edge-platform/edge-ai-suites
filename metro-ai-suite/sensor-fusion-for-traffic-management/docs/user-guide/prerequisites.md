#	Prerequisites and Dependencies

## Prerequisites

- Operating System: [Ubuntu 22.04.1 Desktop LTS](https://old-releases.ubuntu.com/releases/22.04.1/ubuntu-22.04.1-desktop-amd64.iso) (fresh installation) on target system

- Platform

    - Intel® Celeron® Processor 7305E (1C+1R/2C+1R usecase)
    - Intel® Core™ Ultra 7 Processor 165H (4C+4R usecase)
    - Intel® Core™ i7-13700 and Intel® Arc™ A770 Graphics (16C+4R usecase)

- Intel® OpenVINO™ Toolkit

    - Version Type: 2025.2

- RADDet Dataset

    - https://github.com/ZhangAoCanada/RADDet#Dataset

    - A processed data snippet is provided in [demo](../../ai_inference/test/demo/raddet_bin_files)

    - If you want to generate the data independently, refer to this guide: [how_to_get_RADDet_datasets.md](How-To-Get-RADDET-Dataset.md)

        Upon success, bin files will be extracted, save to $RADDET_DATASET_ROOT/bin_files_{VERSION}:

        > NOTE: latest converted dataset version should be: v1.0

- Ensure that proxy settings are configured if target system is within proxy environment

    ```bash
    export http_proxy=<Your-Proxy>
    export https_proxy=<Your-Proxy>
    ```

    ```bash
    sudo vim /etc/environment
    # set proxy in /etc/environment
    # http_proxy=<Your-Proxy>
    # https_proxy=<Your-Proxy>
    ```



### Modules

-   AI Inference Service:

    -   Media Processing (Camera)

    -   Radar Processing (mmWave Radar)

    -   Sensor Fusion

-   Demo Application

#### AI Inference Service

AI Inference Service is based on the HVA pipeline framework. In this SW RI, it includes the functions of DL inference, radar signal processing, and data fusion.

AI Inference Service exposes both RESTful API and gRPC API to clients, so that a pipeline defined and requested by a client can be run within this service.

-   RESTful API: listens to port 50051

-   gRPC API: listens to port 50052
```bash
vim $PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config
...
[HTTP]
address=0.0.0.0
RESTfulPort=50051
gRPCPort=50052
```


#### Demo Application
![Demo-1C1R](./_images/Demo-1C1R.png)
<center>Figure 2. Visualization of 1C+1R results</center>

Currently we support four display types: media, radar, media_radar, media_fusion. 


For system requirements, see [system-req.md](./system-req.md).


## Install Dependencies and Build Project

* install driver related libs

  Update kernel, install GPU and NPU(MTL only) driver.

  ```bash
  bash install_driver_related_libs.sh
  ```

  Note that this step may restart the machine several times. Please rerun this script after each restart until you see the output of `All driver libs installed successfully`.

* install project related libs

  Install Boost, Spdlog, Thrift, MKL, OpenVINO, GRPC, Level Zero, oneVPL etc.

  ```bash
  bash install_project_related_libs.sh
  ```

- set $PROJ_DIR
  ```bash
  cd metro-ai-suite/sensor-fusion-for-traffic-management
  export PROJ_DIR=$PWD
  ```
- prepare global radar configs in folder: /opt/datasets
    ```bash
    sudo ln -s $PROJ_DIR/ai_inference/deployment/datasets /opt/datasets
    ```

- prepare models in folder: /opt/models
    ```bash
    sudo ln -s $PROJ_DIR/ai_inference/deployment/models /opt/models
    ```
- prepare offline radar results for 4C4R/16C4R:
    ```bash
    sudo cp $PROJ_DIR/ai_inference/deployment/datasets/radarResults.csv /opt
    ```
- build project
    ```bash
    bash -x build.sh
    ```
