# Troubleshooting

This page provides troubleshooting steps, FAQs, and resources to help you resolve common
issues. If you encounter any problems with the application not addressed here, check the
[GitHub Issues](https://github.com/open-edge-platform/edge-ai-suites/issues) board. Feel free
to file new tickets there (after learning about the guidelines for [Contributing](https://github.com/open-edge-platform/edge-ai-suites/blob/main/CONTRIBUTING.md)).

## Troubleshooting Steps

1. **Changing the Host IP Address**

   - If you need to use a specific Host IP address instead of the one automatically detected
   during installation, you can explicitly provide it using the following command:

     ```bash
     ./install.sh <application-name> <HOST_IP>
     ```

     Example:
     ```bash
     ./install.sh smart-parking 192.168.1.100
     ```

2. **Containers Not Starting**:
   - Check the Docker logs for errors:
     ```bash
     docker ps -a
     docker logs <CONTAINER_ID>
     ```

3. **Failed Service Deployment**:
   - If unable to deploy services successfully due to proxy issues, ensure the proxy is
   configured in the `~/.docker/config.json`:

     ```json
     {
       "proxies": {
         "default": {
           "httpProxy": "http://your-proxy:port",
           "httpsProxy": "https://your-proxy:port",
           "noProxy": "localhost,127.0.0.1"
         }
       }
     }
     ```

   - After editing the file, restart docker:
     ```bash
     sudo systemctl daemon-reload
     sudo systemctl restart docker
     ```

4. **Video stream not displaying on Grafana UI**
   - If you do not see the video stream because of a URL issue, then ensure that `WEBRTC_URL`
   in Grafana has:

      ```bash
      # When Grafana is opened on https://localhost/grafana
      https://localhost/mediamtx/

      # When Grafana is opened on https://<HOST_IP>/grafana
      https://<HOST_IP>/mediamtx/
      ```

5. **Resolving Time Sync Issues in Prometheus**
  
      If you see the following warning in Prometheus, it indicates a time sync issue.
      
        **Warning: Error fetching server time: Detected xxx.xxx seconds time difference between your browser and the server.**
      
      You can follow the below steps to synchronize system time using NTP.
      
      1. **Install systemd-timesyncd** if not already installed:
      
          ```bash
          sudo apt install systemd-timesyncd
          ```
      
      2. **Check service status**:
      
          ```bash
          systemctl status systemd-timesyncd
          ```
      
      3. **Configure an NTP server** (if behind a corporate proxy):
      
          ```bash
          sudo nano /etc/systemd/timesyncd.conf
          ```
      
          Add:
      
          ```ini
          [Time]
          NTP=corp.intel.com
          ```
      
          Replace `corp.intel.com` with a different ntp server that is supported on your network.
      
      4. **Restart the service**:
      
          ```bash
          sudo systemctl restart systemd-timesyncd
          ```
      
      5. **Verify the status**:
      
          ```bash
          systemctl status systemd-timesyncd
          ```
      
      This should resolve the time discrepancy in Prometheus.  

## Troubleshooting Helm Deployments

1. Deploying with Intel GPU K8S Extension on Intel® Tiber™ Edge Platform

If you're deploying a GPU based pipeline (example: with VA-API elements like `vapostproc`,
`vah264dec` etc., and/or with `device=GPU` in `gvadetect` in `config.json`) with Intel GPU
k8s Extension on Intel® Tiber™ Edge Platform, ensure to set the below details in the file
`helm/values.yaml` appropriately in order to utilize the underlying GPU.

```sh
gpu:
  enabled: true
  type: "gpu.intel.com/i915"
  count: 1
```

2. Deploying without Intel GPU K8S Extension

If you're deploying a GPU based pipeline (example: with VA-API elements like `vapostproc`,
`vah264dec` etc., and/or with `device=GPU` in `gvadetect` in `config.json`) without Intel GPU
k8s Extension, ensure to set the following details in the file `helm/values.yaml` appropriately
in order to utilize the underlying GPU.

```sh
privileged_access_required: true
```

---
> *Intel, the Intel logo and Intel Tiber are trademarks of Intel Corporation or its subsidiaries.*
