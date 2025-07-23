# Get Help

This page provides troubleshooting steps, FAQs, and resources to help you resolve common issues.


## Troubleshooting Steps

1. **Changing the Host IP Address**

   - If you need to use a specific Host IP address instead of the one automatically detected during installation, you can explicitly provide it using the following command:

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
   - If unable to deploy services successfully due to proxy issues, ensure the proxy is configured in the `~/.docker/config.json`:

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

## Support
- **Raise an Issue on GitHub**: [GitHub Issues](https://github.com/open-edge-platform/edge-ai-suites/issues)