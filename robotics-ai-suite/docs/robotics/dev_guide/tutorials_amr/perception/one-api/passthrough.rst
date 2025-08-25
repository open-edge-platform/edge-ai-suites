.. _oneapi_passthrough:

Filtering Point Clouds with a Passthrough Filter
===========================================================

This tutorial demonstrates how to execute passthrough filtering.

.. note::

  This tutorial is applicable for execution for both within inside and outside a |docker| image. It assumes that the
  *pcl-oneapi-tutorials* |deb_pack| is installed, and the user has copied the *tutorial*
  directory from */opt/intel/pcl/oneapi/tutorials/* to a user-writable directory.

#. Prepare the environment:

   .. code-block::

      cd <path-to-oneapi-tutorials>/passthrough


#. ``oneapi_passthrough.cpp`` should be in the directory with following content:

   .. literalinclude:: ../../../../sources/passthrough/oneapi_passthrough.cpp
      :language: cpp
      :linenos:


#. Source the |l_oneapi| environment:

   .. code-block::

      source /opt/intel/oneapi/setvars.sh


#. (Optional) Set up proxy setting to download test data:

   .. code-block::

      export http_proxy="http://<http_proxy>:port"
      export https_proxy="http://<https_proxy>:port"

#. Build the code:

   .. code-block::

      mkdir build && cd build
      cmake ../
      make -j

#. Run the binary:

   .. code-block::

      ./oneapi_passthrough

#. Expected results example:

   .. code-block::

      [oneapi passthrough] PointCloud before filtering: 993419
      [oneapi passthrough] PointCloud after filtering: 328598

Code Explanation
--------------------


Load the example PCD into a PointCloud<PointXYZ>.

.. literalinclude:: ../../../../sources/passthrough/oneapi_passthrough.cpp
   :language: cpp
   :lines: 14-21
   :dedent:

Prepare output buffer for filtered result.

.. literalinclude:: ../../../../sources/passthrough/oneapi_passthrough.cpp
   :language: cpp
   :lines: 23-24
   :dedent:

Starts to compute the result.

.. literalinclude:: ../../../../sources/passthrough/oneapi_passthrough.cpp
   :language: cpp
   :lines: 26-31
   :dedent:

Result (output log):

.. literalinclude:: ../../../../sources/passthrough/oneapi_passthrough.cpp
   :language: cpp
   :lines: 34-35
   :dedent:
