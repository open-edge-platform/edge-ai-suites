Install |lp_amr| |deb_packs|
#################################

This section details steps to install |amr_package_name| |deb_packs|.

.. note::

  Before proceeding, ensure that you have first :doc:`prepared the target system <prepare-system>`.

.. raw:: html

   <br/>

.. tabs::

   .. tab:: Install the toolkit on the target

      .. include:: install-host.rst

   .. tab:: Install in a Docker container (optional)

      .. include:: install-docker.rst

Install one of the following packages based upon your processor type:

* Intel SSE-only CPU instruction accelerated package for Collaborative SLAM (installed by default):

   .. code-block:: bash

      # Required for Intel® Atom® processor-based systems

      sudo apt-get install ros-humble-collab-slam-sse

* Intel AVX2 CPU instruction accelerated package for Collaborative SLAM:

   .. code-block:: bash

      # Works only on Intel® Core™ processor-based systems

      sudo apt-get install ros-humble-collab-slam-avx2

* Intel GPU Level-Zero accelerated package for Collaborative SLAM:

   .. code-block:: bash

      # Works only on 9th, 11th or 12th Generation Intel® Core™ processors with Intel® Iris® Xe Integrated Graphics or Intel® UHD Graphics

      sudo apt-get install ros-humble-collab-slam-lze

   During the installation of the above packages, you will see a dialogue
   asking you for the GPU generation of your system:

   .. figure:: ../images/debconf_liborb-lze.png

   In this dialogue, select the GPU Generation according to the following table
   depending on your processor type. If you are unsure, it's safe to select
   ``genXe``.

   .. table::
      :widths: 30,70

      +-----------------+-------------------------------------------------------------+
      | GPU Generation  | Processors                                                  |
      +=================+=============================================================+
      | ``genXe``       | |core| Ultra Processors                                     |
      |                 |                                                             |
      |                 | 13th Generation |core| Processors                           |
      |                 |                                                             |
      |                 | 12th Generation |core| Processors                           |
      |                 |                                                             |
      |                 | 11th Generation |core| Processors                           |
      |                 |                                                             |
      |                 | |intel| Processor N-series (products formerly Alder Lake-N) |
      +-----------------+-------------------------------------------------------------+
      | ``gen11``       | Products formerly Ice Lake                                  |
      +-----------------+-------------------------------------------------------------+
      | ``gen9``        | Products formerly Skylake                                   |
      +-----------------+-------------------------------------------------------------+

   If you want to redisplay this dialogue, you have to uninstall the
   ``liborb-lze`` package using the commands below. This will also remove
   the packages that depend on the ``liborb-lze`` package.
   Then you can install the ``liborb-lze`` package again and the dialogue will
   be redisplayed:

   .. code-block:: bash

      sudo apt remove --purge liborb-lze
      echo PURGE | sudo debconf-communicate liborb-lze
      sudo apt install liborb-lze

   Since the ``liborb-lze`` package is one of the fundamental dependencies of
   the |lp_amr|, you will have to re-install the ``ros-humble-collab-slam-lze``
   package as described above.
