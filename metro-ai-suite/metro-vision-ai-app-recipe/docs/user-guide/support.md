# Get Help

This page provides troubleshooting steps, FAQs, and resources to help you resolve common issues.

## Resolving Time Sync Issues in Prometheus

If you see the following warning in Prometheus, it indicates a time sync issue.

**Warning: Error fetching server time: Detected xxx.xxx seconds time difference between your browser and the server.**

You can following the below steps to synchronize system time using NTP.

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

## Support
- **Developer Forum**: [Join the community forum](#)
- **Raise an Issue on GitHub**: [GitHub Issues](https://github.com/open-edge-platform/edge-ai-suites/issues)
- **Contact Support**: [Support Page](#)