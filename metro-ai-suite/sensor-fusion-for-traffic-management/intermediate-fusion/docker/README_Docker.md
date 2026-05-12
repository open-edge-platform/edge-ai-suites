# Docker Workflow

The commands below assume this project root is already the current working directory.

Use the published Docker image for the fastest project validation. Build a local image only when you need a custom OpenVINO install tree, local source changes, or Dockerfile changes.

## 1. Install Docker Engine and Docker Compose on Ubuntu

Install [Docker Engine](https://docs.docker.com/engine/install/ubuntu/) and [Docker Compose](https://docs.docker.com/compose/) according to the guide on the official website.

Before you install Docker Engine for the first time on a new host machine, you need to set up the Docker `apt` repository. Afterward, you can install and update Docker from the repository.

1. Set up Docker's `apt` repository.

```bash
# Add Docker's official GPG key:
sudo -E apt-get update
sudo -E apt-get install ca-certificates curl
sudo -E install -m 0755 -d /etc/apt/keyrings
sudo -E curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo -E apt-get update
```

2. Install the Docker packages.

To install the latest version, run:

```bash
sudo -E apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```



3. Set proxy(Optional).

Note you may need to set proxy for docker.

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo vim /etc/systemd/system/docker.service.d/http-proxy.conf

# Modify the file contents as follows
[Service]
Environment="HTTP_PROXY=http://proxy.example.com:8080"
Environment="HTTPS_PROXY=http://proxy.example.com:8080"
Environment="NO_PROXY=localhost,127.0.0.1"
```



Then restart docker:

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```



4. Verify that the installation is successful by running the `hello-world` image:

```bash
sudo docker run hello-world
```

This command downloads a test image and runs it in a container. When the container runs, it prints a confirmation message and exits.

5. Add user to group

```bash
sudo usermod -aG docker $USER
newgrp docker
```

## 2. Install the corresponding driver on the host

```bash
bash install_driver_related_libs.sh
```

**If driver are already installed on the machine, you don't need to do this step.**

## 3. Recommended: pull and run the published image

> **Note that the default username is `tfcc` and password is `intel` in the docker image.**

When the published image is available, pull the `tfcc:bevfusion` image and run it directly.

For example:

```bash
docker pull tfcc:bevfusion
```

If you already pulled or built the image locally, you do not need to rebuild it. You can run it directly.

### Run the published image

```bash
bash docker/run_docker.sh tfcc:bevfusion
# After the run completes, the container ID is printed. You can also find it with docker ps.
```

### Enter docker

Get the container id by command below:

```bash
docker ps -a
```

And then enter docker by command below:

```bash
docker exec -it <container id> /bin/bash
```

### Copy dataset

If you want to copy dataset or other files to docker, you can use the command below:

```bash
docker cp /path/to/dataset <container id>:/path/to/dataset
```

## 4. Run automated tests inside Docker

Use the published image for the quickest validation:

```bash
bash autotest_docker.sh --image tfcc:bevfusion
```

This uses the dataset path already visible inside the container. The default is `/home/tfcc/bevfusion/data/v2xfusion/dataset`, and you can override it with `--container-dataset-path`.

To copy a dataset from the host into the container for the test run:

```bash
bash autotest_docker.sh --image tfcc:bevfusion --dataset-path /path/to/kitti_dataset
```

If you already pulled or built the default image tag `tfcc:bevfusion`, you can omit `--image`:

```bash
bash autotest_docker.sh
```

If the image is missing and you want to build it locally instead of pulling it:

```bash
bash autotest_docker.sh \
  --build-image \
  --custom-openvino-install-dir /path/to/custom_openvino/install
```

Additional arguments after `--` are forwarded to `autotest.sh` inside the container. For example, to restore live per-binary output:

```bash
bash autotest_docker.sh --image tfcc:bevfusion -- --verbose
```

If `--dataset-path` is provided, the script copies that host dataset into the container and uses it for the inner autotest run. If `--dataset-path` is omitted, the script uses `--container-dataset-path` directly.

The helper copies the generated container logs back to `docker_autotest_logs/<timestamp>/` by default and finishes with a final `AUTOTEST_DOCKER_RESULT ...` line that includes the copied host log paths.

## 5. Optional: build and run a local image through scripts

Skip this section if the published image is already sufficient for your validation.

Before building locally, you may pre-pull the base layer:

```bash
docker pull ubuntu:24.04
```

> The Docker image now expects a host-side custom OpenVINO install tree that already contains the required custom ops. Pass the install root that directly contains `setupvars.sh`; the build copies it into `/opt/intel/openvino` inside the image.
>
> The current Dockerfile also pins the Intel GPU compute userspace to the validated IGC `2.32.7+21184` and compute-runtime `26.14.37833.4` packages, instead of mixing GPU runtime pieces from multiple package sources.

If you do not already have a host-side custom OpenVINO install tree, generate
one first. The helper script will clone upstream OpenVINO 2026.1.0 into
`--ov-dir` if the checkout is missing:

```bash
bash install_custom_openvino.sh --ov-dir /path/to/openvino
# Result: /path/to/openvino/install
```

The install root must directly contain `setupvars.sh` and `runtime/lib/`.

### Build the local image

Usage:

```bash
bash docker/build_docker.sh <CUSTOM_OPENVINO_INSTALL_DIR> [IMAGE_TAG] [DOCKERFILE] [BASE] [BASE_VERSION]
```

Example:

```bash
bash docker/build_docker.sh /path/to/custom_openvino/install
```

If you want to override the image name or base image settings, append them after the required custom OpenVINO path:

```bash
bash docker/build_docker.sh /path/to/custom_openvino/install tfcc:bevfusion Dockerfile.dockerfile ubuntu 24.04
```

Requirements for `CUSTOM_OPENVINO_INSTALL_DIR`:

```bash
ls /path/to/custom_openvino/install/setupvars.sh
ls /path/to/custom_openvino/install/runtime/lib/
```

The directory can live anywhere on the host. `build_docker.sh` forwards it as an extra BuildKit build context, so you do not need to copy it into this repository first.

### Run the locally built image

Usage:

```bash
bash docker/run_docker.sh <DOCKER_IMAGE, default tfcc:bevfusion>
```

Example:

```bash
bash docker/run_docker.sh tfcc:bevfusion
```

## 6. Optional: Docker Compose workflow for local images

The Compose file supports both the published `tfcc:bevfusion` image and local rebuilds. Use `docker compose pull` or `docker compose up` when the published image is available. Use `docker compose up --build` when you want to rebuild from local sources.

Modify `proxy`, `VIDEO_GROUP_ID`, and `RENDER_GROUP_ID` in `.env`.

```bash
# proxy settings
https_proxy=
http_proxy=
# docker image name
DOCKER_IMAGE=tfcc:bevfusion
# base image settings
BASE=ubuntu
BASE_VERSION=24.04
# custom OpenVINO install directory on the host
CUSTOM_OPENVINO_INSTALL_DIR=/absolute/path/to/custom_openvino/install
# group IDs for various services
VIDEO_GROUP_ID=44
RENDER_GROUP_ID=110
# display settings
DISPLAY=$DISPLAY
```

`CUSTOM_OPENVINO_INSTALL_DIR` is only required when you want Compose to build the image locally. During `docker compose build` or `docker compose up --build`, Compose forwards that host directory as an additional build context and the image copies it to `/opt/intel/openvino`.

You can get `VIDEO_GROUP_ID` and `RENDER_GROUP_ID` with the following commands:

```bash
# VIDEO_GROUP_ID
echo $(getent group video | awk -F: '{printf "%s\n", $3}')
# RENDER_GROUP_ID
echo $(getent group render | awk -F: '{printf "%s\n", $3}')
```

### Build and run with Compose

Usage:

```bash
cd docker
docker compose pull bevfusion
docker compose up <service-name> -d
```

Example:

```bash
cd docker
docker compose pull bevfusion
docker compose up bevfusion -d
```

Use `docker compose up --build bevfusion -d` when you need Compose to rebuild the image from local sources.

### Enter docker

Usage:

```bash
docker compose exec <service-name> /bin/bash
```

Example:

```bash
docker compose exec bevfusion /bin/bash
```

### Copy dataset

Find the container name or ID:

```bash
docker compose ps
```

Sample output:

```bash
NAME                 IMAGE            COMMAND       SERVICE     CREATED              STATUS                        PORTS
docker-bevfusion-1   tfcc:bevfusion   "/bin/bash"   bevfusion   About a minute ago   Up About a minute (healthy)
```

Copy dataset:

```bash
docker cp /path/to/dataset docker-bevfusion-1:/path/to/dataset
```