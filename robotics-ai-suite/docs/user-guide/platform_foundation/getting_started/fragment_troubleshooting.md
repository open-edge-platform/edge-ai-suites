# Installation Troubleshooting

## Support Forum

If you encounter difficulties, visit the [Support Forum](https://community.intel.com/t5/Edge-Software-Catalog/bd-p/EdgeSoftwareCatalog) for assistance.

## APT Package Manager

If the APT package manager is unable to connect to the repositories, follow these APT troubleshooting tips:

- Make sure that the system has network connectivity.
- Make sure that port 80 is not blocked by a firewall.
- Configure an APT proxy (if network traffic routes through a proxy server).

    - To configure an APT proxy, add the following lines to a file at
      `/etc/apt/apt.conf.d/proxy.conf` (replace the placeholder as per your specific user and proxy server)::

      ```bash
      Acquire:http:Proxy "http://user:password@proxy.server:port/";
      Acquire:https:Proxy "http://user:password@proxy.server:port/";
      ```

    - To ensure proper proxy settings for other tools required during the package installation
      add the the required proxy settings to `/etc/environment`:

      ```bash
      http_proxy=http://user:password@proxy.server:port
      https_proxy=http://user:password@proxy.server:port
      no_proxy="localhost,127.0.0.1,127.0.0.0/8"
      ```

     After setting the proxy values in `/etc/apt/apt.conf.d/proxy.conf` and `/etc/environment`
     you will have to reboot the device, so these settings become effective.