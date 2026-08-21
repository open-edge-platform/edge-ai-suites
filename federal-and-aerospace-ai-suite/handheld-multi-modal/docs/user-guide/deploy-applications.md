# Handheld Multi-Modal Application Deployment

This guide provides instructions on how to deploy the Handheld Multi-Modal application on a
local machine.

## (Optional) Configuring the Proxy

> **Note**: If not using proxy servers, skip to [Deploying the Application](#deploying-the-application).

Depending on the system's network configuration, you may need an additional proxy configuration.
Ensure that `/etc/environment` contains proxy variables; replace `proxy-example:123` with a
valid proxy for the local environment:

```bash
sudo tee -a /etc/environment > /dev/null <<EOF
http_proxy="http://proxy-example:123"
https_proxy="http://proxy-example:123"
ftp_proxy="http://proxy-example:123"
no_proxy="localhost,127.0.0.1,10.0.0.0/8,192.0.0.0/8,fedaero.intel.com,vippet,grafana,metrics-manager"
EOF

source /etc/environment
```

Configure the proxy for the Docker client:

```bash
mkdir -p ~/.docker
tee -a ~/.docker/config.json > /dev/null <<EOF
{
    "proxies": {
        "default": {
            "httpProxy":  "http://proxy-example:123",
            "httpsProxy": "http://proxy-example:123",
            "noProxy":    "localhost,127.0.0.1,10.0.0.0/8,192.0.0.0/8,fedaero.intel.com,vippet,grafana,metrics-manager"
        }
    }
}
EOF
```

Configure the proxy for Docker containers:

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo tee /etc/systemd/system/docker.service.d/http-proxy.conf > /dev/null <<EOF
[Service]
Environment="HTTP_PROXY=http://proxy-example:123"
Environment="HTTPS_PROXY=http://proxy-example:123"
Environment="NO_PROXY=localhost,127.0.0.1,10.0.0.0/8,192.0.0.0/8,fedaero.intel.com,vippet,grafana,metrics-manager"
EOF
```

Restart the Docker daemon:

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

Verify the Docker daemon's proxy configurations (sample output below):

```text
docker info|grep -i PROXY
 HTTP Proxy: http://proxy-example:123
 HTTPS Proxy: http://proxy-example:123
 No Proxy: localhost,127.0.0.1,10.0.0.0/8,192.0.0.0/8,fedaero.intel.com,vippet,grafana,metrics-manager
```

## Deploying the Application

Download the compressed file:

```bash
curl -OjL https://github.com/open-edge-platform/edge-ai-suites/releases/download/fedaero-latest/handheld-multi-modal.zip
```

Decompress the downloaded file:

```bash
unzip handheld-multi-modal.zip
```

Run the script that installs all dependencies, downloads models, and starts applications.
During installation, a single prompt asking to accept licenses of models will appear.
Depending on network bandwidth, it takes around 10-15 minutes. If an error occurs during
installation, see the [proxy configuration step](#optional-configure-the-proxy):

```bash
cd handheld-multi-modal
./run.sh up
```

## Verifying the installation

After the script finishes, verify that the containers are running (sample output below):

```text
docker ps
CONTAINER ID   IMAGE                                                   COMMAND                  CREATED          STATUS                             PORTS                                                                                                                                   NAMES
45aeb6ad8884   nginx:alpine                                            "/docker-entrypoint.…"   27 seconds ago   Up 25 seconds                      127.0.0.1:443->443/tcp, 127.0.0.1:5443->5443/tcp, 127.0.0.1:7443->7443/tcp, 80/tcp, 127.0.0.1:8443->8443/tcp                            nginx-https
1cf974e6c425   ghcr.io/open-webui/open-webui:v0.11.0-slim               "bash start.sh"          27 seconds ago   Up 25 seconds (health: starting)   8080/tcp                                                                                                                                open-webui
90c0db070f36   whisper-stt:latest                                      "/entrypoint.sh pyth…"   27 seconds ago   Up 26 seconds                      5000/tcp                                                                                                                                whisper-stt
ee1cef103480   grafana/grafana:13.1.0-25893932881                      "/run.sh"                27 seconds ago   Up 26 seconds                      3000/tcp                                                                                                                                grafana
231fd29c88d8   openvino/model_server:latest-gpu                        "/ovms/bin/ovms --re…"   27 seconds ago   Up 26 seconds                                                                                                                                                              ovms
3dc8dfefa60e   intel/vippet-ui:2026.1.0-20260512-weekly                "/docker-entrypoint.…"   34 seconds ago   Up 27 seconds                      0.0.0.0:80->80/tcp, [::]:80->80/tcp                                                                                                     ui
d1ec3f394245   intel/vippet-app:2026.1.0-20260512-weekly               "./entrypoint.sh"        34 seconds ago   Up 33 seconds (healthy)            0.0.0.0:7860->7860/tcp, [::]:7860->7860/tcp                                                                                             vippet
9fa7733f0cc4   bluenviron/mediamtx:1.15.6                              "/mediamtx"              34 seconds ago   Up 33 seconds                      0.0.0.0:8554->8554/tcp, [::]:8554->8554/tcp, 0.0.0.0:8189->8189/udp, [::]:8189->8189/udp, 0.0.0.0:8889->8889/tcp, [::]:8889->8889/tcp   mediamtx
76d9c62a039b   intel/vippet-onvif-discovery:2026.1.0-20260512-weekly   "/bin/sh -c 'python …"   34 seconds ago   Up 33 seconds                                                                                                                                                              onvif-discovery
f9d9fc705f29   intel/metrics-manager:2026.1.0-20260508-weekly          "/entrypoint.sh"         34 seconds ago   Up 33 seconds (healthy)            0.0.0.0:9090->9090/tcp, [::]:9090->9090/tcp, 8186/tcp, 0.0.0.0:9273->9273/tcp, [::]:9273->9273/tcp                                      metrics-manager
c7e676f86e1b   intel/model-download:2026.1.0-20260505-weekly           "/opt/entrypoint.sh …"   34 seconds ago   Up 33 seconds (healthy)            0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
```

> **Note**: After a system restart, run `./run up` from the `handheld-multi-modal` directory to start the applications again.

## Accessing Application User Interface

This composite application exposes multiple endpoints through the NGINX TLS reverse proxy.
They are bound to localhost only and are not exposed on any external IP address.
Since the intended use is on handheld devices, the applications do not provide authentication
or authorization.

> **Notice**:
> The "self-signed certificate" browser warning is expected.
> Modern browsers require HTTPS to enable microphone input used by Open WebUI and
  Speech To Text services, therefore, the NGINX reverse proxy uses the certificate to ensure
  TLS transport on the `localhost` bound addresses.

To add certificate to trust pool, open Browser of your choice, navigate to `Settings->Certificates->Manage certificates` page, select `Authorities` tab and click `Import`. In file explorer navigate to folder that contains Handheld Multi-Modal Application and select `data/nginx-certs/ca-cert.pem` file. Select `Trust this CA to identify websites` checkbox and click `ok`.


| Service | URL | Notes |
|---------|-----|-------|
| Single pane page | https://localhost:443 | via NGINX reverse proxy |
| Visual Pipeline and Platform Evaluation Tool UI | https://localhost:1443 | via NGINX reverse proxy |
| Open WebUI | https://localhost:8443 | Conversational Agent backed by LLM — browser microphone enabled (via NGINX reverse proxy) |
| Whisper speech-to-text service | https://localhost:5443 | Speech-to-text — browser microphone enabled (via NGINX reverse proxy) |
| Grafana dashboard | https://localhost:7443 | Pre-provisioned dashboards (via NGINX reverse proxy) |


<!--
Source: [Endpoints](https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-and-aerospace-ai-suite/handheld-multi-modal/README.md#endpoints)
-->

### ViPPET

After opening main page of ViPPET, user can select one of several options available in ViPPET:
1) Pipelines - to check and run one of predefined pipelines and understand how it works. Predefined pipelines will show video output will output video stream that shows how model works as well as small subset of system metrics during execution of pipeline. It also exposes option to add new custom pipeline for advanced users, but it might require additional input from other options. 
2) Benchmarks - allows to compare performance of pipeline on diffrent combinations of supported hardware (CPU/NPU/GPU/NPU+GPU) to find out best device for specific pipeline.
3) Models - exposes list of available models that could be used in pipeline as well as import functionality for models
4) Video/Images/Cameras - allows to configure source of data that could be used in pipeline.

### Open WebUI

Main page exposes chat with default AI model, where user can ask questions. If initial response isn't sufficent, chat with AI model can be continued in the same window, which will keep context. If question is related to attachment(s), such as file, web-page or other chat, it could be added by clicking on `+` sign and selecting corresponding option.
If user wants to change topic, it is recommended to open `New Chat` windows and start new chat to keep AI model context clean, as it improves results.

### Whisper

After entering main page of Whisper, there are 2 options to upload audio for transcription:
1) By uploading audio file in one of supported audio format ("flac", "m4a", "mp3", "mp4", "ogg", "wav", "webm") by clicking on corresponding section in UI and selecting file in file explorer or by drag-and-dropping file into that section.
2) By recording audio from microphone. Click on round `record` button, allow Whisper access to microphone and start talking into microphone.
In both cases, transcription text will appear on lower part of the page in real-time in parts, as soon as Whisper will complete transcription of part of recording. Once whole recording is transcribed, additional section that show duration and ratio of transcription will appear.

### Grafana

By-default, main page shows generic metrics from system, such as CPU/NPU and power consumption. To switch to more detailed, per-application, view navigate to `Dashboards->Panther Lake Live Dashboard` dashboard. On this dashboard, most of metrics will be either empty or will not display any value, since metrics are gathered in real-time and other applications must execute workload to generate metrics. Metrics map to other handheld applcications as follows:
1) `Frame Rate Over Time` and `Latest Pipeline Frame Rate Average` are from ViPPET.
2) `LLM Number of Responses Generated` and `LLM Number of Responses Generated` are from Open WebUI.
3) `Speech to text Processing Ratio Last` and `Speech To Text Processing Ratio` are from Whisper.
Metrics are not persisted in any database, so refresh of page will reset ALL gathered metrics.