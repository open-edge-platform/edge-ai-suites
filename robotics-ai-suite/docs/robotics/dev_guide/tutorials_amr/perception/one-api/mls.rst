.. _oneapi_sample_mls:

Surface Reconstruction with |oneapi| Moving Least Squares (MLS)
=============================================================================

MLS creates a 3D surface from a point cloud through either down-sampling or up-sampling techniques. |l_oneapi|\'s MLS is based on the original MLS API. Differences between the two:

-  oneapi MLS calculates with 32-bit float instead of 64-bit double.

-  oneapi MLS's surface is constructed as a set of indices grouped into
   multiple blocks. This consumes more system memory than the original version.
   Control the block size with ``setSearchBlockSize``.

-  oneapi MLS improves the performance of all up-sampling
   methods.

-  The oneapi namespace must be appended to the original MovingLeastSquares
   class.

See `resampling.rst
<https://github.com/PointCloudLibrary/pcl/blob/master/doc/tutorials/content/resampling.rst>`__
for details.

.. note::

  This tutorial is applicable for execution both within inside and outside a |docker| image. It assumes that the
  ``pcl-oneapi-tutorials`` |deb_pack| is installed, and the user has copied the *tutorial*
  directory from */opt/intel/pcl/oneapi/tutorials/* to a user-writable directory.

#. Prepare the environment:

   .. code-block::

      cd <path-to-oneapi-tutorials>/mls


#. ``oneapi_mls.cpp`` should be in the directory with following content:

   .. literalinclude:: ../../../../sources/mls/oneapi_mls.cpp
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

      ./oneapi_mls

#. The reconstructed surface saves as ``bun0-mls.pcd``.  To view the smoothed surface

   .. code-block::

      pcl_viewer bun0-mls.pcd


Code Explanation
--------------------

|oneapi| MLS requires this header.

.. literalinclude:: ../../../../sources/mls/oneapi_mls.cpp
   :language: cpp
   :lines: 3-4
   :dedent:

Load the test data into a PointCloud<PointXYZ> (these fields are
mandatory; other fields are allowed and preserved).

.. literalinclude:: ../../../../sources/mls/oneapi_mls.cpp
   :language: cpp
   :lines: 15-18
   :dedent:

Compare to original version, append oneapi namespace to original MovingLeastSquares class. 
The first template type is used for the input and output cloud. Only the XYZ
dimensions of the input are smoothed in the output.

.. literalinclude:: ../../../../sources/mls/oneapi_mls.cpp
   :language: cpp
   :lines: 25-26
   :dedent:

If normal estimation is required:

.. literalinclude:: ../../../../sources/mls/oneapi_mls.cpp
   :language: cpp
   :lines: 28
   :dedent:

The maximum polynomial order is five. See the code API (`pcl:MovingLeastSquares
<http://docs.ros.org/en/hydro/api/pcl/html/classpcl_1_1MovingLeastSquares.html>`__)
for default values and additional parameters to control the smoothing process.

.. literalinclude:: ../../../../sources/mls/oneapi_mls.cpp
   :language: cpp
   :lines: 30-34
   :dedent:

Perform reconstruction

.. literalinclude:: ../../../../sources/mls/oneapi_mls.cpp
   :language: cpp
   :lines: 36-37
   :dedent:
