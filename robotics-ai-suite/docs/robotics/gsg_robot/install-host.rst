#. Ensure you have successfully followed the steps to :ref:`install-ros-ros-version`:

   .. code-block:: bash

      apt list --installed | grep ros-humble-ros-base

   The output should look similar to this (versions may differ):

   .. code-block:: console

      ros-humble-ros-base/jammy,now 0.10.0-1jammy.20240217.113903 amd64 [installed,automatic]

#. Before using the |amr_package_name| APT repositories, update the APT packages list:

   .. code-block:: bash

      sudo apt update

   The APT package manager will download the latest list of packages available for all configured repositories.

      .. figure:: ../images/download/apt-update.png

   .. note::

      If the APT package manager is unable to connect to the repositories, follow these APT troubleshooting tips:

      * Make sure that the system has network connectivity.
      * Make sure that port 80 is not blocked by a firewall.
      * Configure an APT proxy (if network traffic routes through a proxy server).

         To configure an APT proxy, add the following lines to a file at
         `/etc/apt/apt.conf.d/proxy.conf` (replace the placeholder as per your specific user and proxy server)::

            Acquire:http:Proxy "http://user:password@proxy.server:port/";
            Acquire:https:Proxy "http://user:password@proxy.server:port/";

         To ensure proper proxy settings for other tools required during the package installation
         add the the required proxy settings to `/etc/environment`::

            http_proxy=http://user:password@proxy.server:port
            https_proxy=http://user:password@proxy.server:port
            no_proxy="localhost,127.0.0.1,127.0.0.0/8"

         After setting the proxy values in `/etc/apt/apt.conf.d/proxy.conf` and `/etc/environment`
         you will have to reboot the device, so these settings become effective.

.. tabs::

   .. tab:: Install default toolkit packages

      .. include:: install-default.rst

   .. tab:: Install individual packages (optional)

      .. include:: install-individual.rst
