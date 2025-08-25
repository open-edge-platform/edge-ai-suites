.. _greedy_triangulation_openmp:

Fast Triangulation of Unordered Point Clouds (OpenMP Version)
=================================================================

This tutorial explains how to run a greedy surface triangulation algorithm (OpenMP version) on a
PointCloud with normals, to obtain a triangle mesh based on projections of the
local neighborhoods. The OpenMP version divides the point cloud into multiple segments and invokes
the original version of the greedy surface triangulation based on the segment count.  By running the
segments independently and concurrently, there will be a disjoint result between each segment.
To overcome the disjoint issue, additional overlap segments are created to go through greedy surface
triangulation and combine with other processed segments.

.. note::

  The  output of OpenMP version may differ from serial version of greedy projection
  triangulation.


Background: Algorithm and Parameters
---------------------------------------

Refer to original `greedy_triangulation <https://pointclouds.org/documentation/tutorials/greedy_projection.html>`__
for more detail original greedy triangulation parameters.  All greedy triangulation parameters are supported except ``getPointStates()``,
``getPartIDs()``, ``getSFN()`` and ``getFFN()``.

Additional parameters are defined to provide control segments and overlap.

* *setNumberofThreads(unsigned)* controls how many segments are created from the input point cloud.
  Each segment size is determined using the formula (maximum x - minimum x) / number of threads, and
  all segment sizes are equal. Each segment will be assigned to a CPU thread/core. It is recommended
  to obtain the number of threads/cores using ``omp_get_max_threads()``.

* *setBlockOverlapPercentage(double)* controls how wide to create the overlap region among two
  segments.  The overlap region is this parameter percentage multiply the size of segment.  If there
  is still gap between segments, can overcome by increase the overlap percentage.

* *setRemoveDuplicateMesh(bool)* controls whether to clean up the duplicate point cloud and polygons
  after combining all the segments output from GP3.

.. note::

  This tutorial is applicable for execution for both within inside and outside a |docker| image. It assumes that the
  *pcl-oneapi-tutorials* |deb_pack| is installed, and the user has copied the *tutorial*
  directory from */opt/intel/pcl/oneapi/tutorials/* to a user-writable directory.

#. Prepare the environment:

   .. code-block::

      cd <path-to-oneapi-tutorials>/greedy_projection


#. ``greedy_projectoin.cpp`` should be in the directory with following content:

   .. literalinclude:: ../../../../sources/greedy_projection/greedy_projection.cpp
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

    ./greedy_projection

#. Output:

   The program will save the output as "``mesh.vtk``".  View the VTK file by:

   .. code-block::

    pcl_viewer mesh.vtk


Code Explanation
-----------------

As the example PCD has only XYZ coordinates, load it into a PointCloud<PointXYZ>.

.. literalinclude:: ../../../../sources/greedy_projection/greedy_projection.cpp
   :language: cpp
   :lines: 13-17
   :dedent:

The method requires normals, so normals are estimated using the standard method from PCL.

.. literalinclude:: ../../../../sources/greedy_projection/greedy_projection.cpp
   :language: cpp
   :lines: 19-28
   :dedent:

Since coordinates and normals are required to be in the same PointCloud, a PointNormal type point cloud is
created.

.. literalinclude:: ../../../../sources/greedy_projection/greedy_projection.cpp
   :language: cpp
   :lines: 30-33
   :dedent:

The lines below deals with the initialization of the required objects. In the OpenMP version, include
*<pcl/oneapi/surface_omp/gp3.h>* and declare the class by appending *OMP* to the original class."

.. literalinclude:: ../../../../sources/greedy_projection/greedy_projection.cpp
   :language: cpp
   :lines: 35-41
   :dedent:

The lines below set the parameters, as explained above, to configure the algorithm.

.. literalinclude:: ../../../../sources/greedy_projection/greedy_projection.cpp
   :language: cpp
   :lines: 43-56
   :dedent:

The lines below set the input objects and perform the actual triangulation.

.. literalinclude:: ../../../../sources/greedy_projection/greedy_projection.cpp
   :language: cpp
   :lines: 59-61
   :dedent:
