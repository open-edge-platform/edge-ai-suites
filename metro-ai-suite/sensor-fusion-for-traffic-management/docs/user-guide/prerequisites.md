#	Prerequisites and Dependencies

## Prerequisites

- Operating System

    - [Ubuntu 24.04.2 Desktop LTS](https://old-releases.ubuntu.com/releases/24.04.2/ubuntu-24.04.2-desktop-amd64.iso) (fresh installation) on Intel® Core™ Ultra 7 265H platform
    -  [Ubuntu 24.10](https://releases.ubuntu.com/24.10/ubuntu-24.10-desktop-amd64.iso) (fresh installation) on Intel® Core™ i7-13700 and Intel® B580 Graphics platform

- Platform

    - Intel® Core™ Ultra 7 265H + Ubuntu24.04 (2C+1L/4C+2L usecase)
    - Intel® Core™ i7-13700 and Intel® B580 Graphics + Ubuntu24.10 (8C+4L/12C+2L usecase)
    
- Intel® OpenVINO™ Toolkit

    - Version Type: 2025.2

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
    -   Lidar Processing
    -   Sensor Fusion
    
-   Demo Application

#### AI Inference Service

AI Inference Service is based on the HVA pipeline framework. In this SW RI, it includes the functions of DL inference, radar signal processing, and data fusion.

AI Inference Service exposes both RESTful API and gRPC API to clients, so that a pipeline defined and requested by a client can be run within this service.

-   RESTful API: listens to port 50021

-   gRPC API: listens to port 50052
```bash
vim $PROJ_DIR/ai_inference/source/low_latency_server/AiInference.config
...
[HTTP]
address=0.0.0.0
RESTfulPort=50021
gRPCPort=50052
```


#### Demo Application
![Demo-2C1L](./_images/Demo-2C1L.png)
<center>Figure 1. Visualization of 2C+1L results</center>

Currently we support four display types: media, lidar, media_lidar, media_fusion. 


For system requirements, see [system-req.md](./system-req.md).


## Install Dependencies and Build Project

* install driver related libs

  Update kernel, install GPU driver.

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
- build liblidar.so
  ```bash
  cd $PROJ_DIR/ai_inference/liblidar
  rm liblidar.so
  bash build.sh
  ```
- prepare global radar configs in folder: /opt/datasets
    ```bash
    sudo ln -s $PROJ_DIR/ai_inference/deployment/datasets /opt/datasets
    ```

- prepare models in folder: /opt/models
    ```bash
    sudo ln -s $PROJ_DIR/ai_inference/deployment/models /opt/models
    ```
- build project
    ```bash
    bash -x build.sh
    ```
