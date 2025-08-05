.. _oneapi_sample_consensus:

Identifying Models and Extracting Parameters in 3D Point Clouds
=============================================================================

This tutorial guides you through the process of detecting a plane model within a 3D point cloud.

.. note::

  This tutorial is applicable for execution both within inside and outside a |docker| image. It- assumes that the
  *pcl-oneapi-tutorials* |deb_pack| is installed, and the user has copied the *tutorial*
  directory from */opt/intel/pcl/oneapi/tutorials/* to a user-writable directory.

#. Prepare the environment:

   .. code-block::

      cd <path-to-oneapi-tutorials>/sample_consensus


#. ``oneapi_sample_consensus.cpp`` should be in the directory with following content:

   .. literalinclude:: ../../../../sources/sample_consensus/oneapi_sample_consensus.cpp
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

      ./oneapi_sample_consensus

#. Expected results example:

   .. code-block::

      input cloud size: 307200
      inliers size    : 77316
      plane model coefficient: -0.0789502, -0.816661, -0.571692, 0.546386
      Optimized coefficient  : -0.0722213, -0.818286, -0.570256, 0.547587


Code Explanation
--------------------

Load the test data from GitHub* into a PointCloud<PointXYZ>.

.. literalinclude:: ../../../../sources/sample_consensus/oneapi_sample_consensus.cpp
   :language: cpp
   :lines: 49-57
   :dedent:

Create GPU input and output device arrays, and load point cloud data into the
input device array.

.. literalinclude:: ../../../../sources/sample_consensus/oneapi_sample_consensus.cpp
   :language: cpp
   :lines: 59-62
   :dedent:

Start computing the model.

.. literalinclude:: ../../../../sources/sample_consensus/oneapi_sample_consensus.cpp
   :language: cpp
   :lines: 65-69
   :dedent:

Result (best model):

.. literalinclude:: ../../../../sources/sample_consensus/oneapi_sample_consensus.cpp
   :language: cpp
   :lines: 72-73
   :dedent:

Result (coefficient model):

.. literalinclude:: ../../../../sources/sample_consensus/oneapi_sample_consensus.cpp
   :language: cpp
   :lines: 76-77
   :dedent:

Result (inliers model):

.. literalinclude:: ../../../../sources/sample_consensus/oneapi_sample_consensus.cpp
   :language: cpp
   :lines: 80-85
   :dedent:

Result (refined coefficient model):

.. literalinclude:: ../../../../sources/sample_consensus/oneapi_sample_consensus.cpp
   :language: cpp
   :lines: 88-89
   :dedent:

Result (output log):

.. literalinclude:: ../../../../sources/sample_consensus/oneapi_sample_consensus.cpp
   :language: cpp
   :lines: 92-95
   :dedent:
