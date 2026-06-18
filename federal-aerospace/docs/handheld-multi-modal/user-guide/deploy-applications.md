# Handheld Multi-Modal Application Deployment

This guide provides instructions on how to deploy the Handheld Multi-Modal application on a
local machine.

## (Optional) Configure the Proxy

Depending on the system's network configuration, you may need an additional proxy configuration.
Ensure that `/etc/environment` contains proxy variables; replace `proxy-example:123` with a
valid proxy for the local environment:

```bash
sudo tee -a /etc/environment > /dev/null <<EOF
export http_proxy="http://proxy-example:123"
export https_proxy="http://proxy-example:123"
export ftp_proxy="http://proxy-example:123"
export no_proxy="localhost,127.0.0.1,10.0.0.0/8,192.0.0.0/8,fedaero.intel.com,vippet,grafana,metrics-manager"
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

## Deploy the Application

Download the compressed file:

```bash
curl -OjL https://github.com/open-edge-platform/edge-ai-suites/releases/download/v2026.1.0/handheld-multi-modal.zip
```

Decompress the downloaded file:

```bash
unzip handheld-multi-modal.zip
```

Run the script that installs all dependencies, downloads models, and starts applications.
Depending on network bandwidth, it takes around 10-15 minutes. If an error occurs during
installation, see the [proxy configuration step](#optional-configure-the-proxy):

```bash
cd handheld-multi-modal
./run up
```

After the script finishes, verify that the containers are running (sample output below):

```text
docker ps
CONTAINER ID   IMAGE                                                   COMMAND                  CREATED          STATUS                             PORTS                                                                                                                                   NAMES
45aeb6ad8884   nginx:alpine                                            "/docker-entrypoint.…"   27 seconds ago   Up 25 seconds                      127.0.0.1:443->443/tcp, 127.0.0.1:5443->5443/tcp, 127.0.0.1:7443->7443/tcp, 80/tcp, 127.0.0.1:8443->8443/tcp                            nginx-https
1cf974e6c425   ghcr.io/open-webui/open-webui:v0.9.6-slim               "bash start.sh"          27 seconds ago   Up 25 seconds (health: starting)   8080/tcp                                                                                                                                open-webui
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

After applications are deployed, see [Endpoints](https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.1.0/federal-aerospace/apps/handheld-multi-modal/README.md#endpoints)
to access a specific application. The applications do not provide authentication or
authorization, hence are only available on the `localhost` and are not exposed under any
external IP address.
