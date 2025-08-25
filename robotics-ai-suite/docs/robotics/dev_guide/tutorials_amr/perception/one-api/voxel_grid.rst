.. _oneapi_voxel_grid:

Downsampling 3D Point Clouds with a Voxelized Grid
===========================================================

This tutorial covers the process of downsampling / reducing the number of points in a 3D point cloud through a voxelized grid approach.

.. note::

  This tutorial is applicable for execution both within inside and outside a |docker| image. It assumes that the
  *pcl-oneapi-tutorials* |deb_pack| is installed, and the user has copied the *tutorial*
  directory from */opt/intel/pcl/oneapi/tutorials/* to a user-writable directory.


#. Prepare the environment:

   .. code-block::

      cd <path-to-oneapi-tutorials>/voxel_grid


#. ``oneapi_voxel_grid.cpp`` should be in the directory with following content:

   .. literalinclude:: ../../../../sources/voxel_grid/oneapi_voxel_grid.cpp
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

      ./oneapi_voxel_grid

#. Expected results example:

   .. code-block::

      [oneapi voxel grid] PointCloud before filtering: 460400
      [oneapi voxel grid] PointCloud after filtering: 141525


Code Explanation
--------------------

Now, let's explain the code in detail.

First, load the example PCD into a PointCloud<PointXYZ>.

.. literalinclude:: ../../../../sources/voxel_grid/oneapi_voxel_grid.cpp
   :language: cpp
   :lines: 13-20
   :dedent:

Then prepare output buffer for filtered result.

.. literalinclude:: ../../../../sources/voxel_grid/oneapi_voxel_grid.cpp
   :language: cpp
   :lines: 22-23
   :dedent:

Next, starts to compute the result.

.. literalinclude:: ../../../../sources/voxel_grid/oneapi_voxel_grid.cpp
   :language: cpp
   :lines: 25-30
   :dedent:

Result(output log).

.. literalinclude:: ../../../../sources/voxel_grid/oneapi_voxel_grid.cpp
   :language: cpp
   :lines: 32-34
   :dedent:
