.. _oneapi_kdtree:

Performing KdTree Search using oneAPI KdTree FLANN
===================================================

OneAPI KdTree is similar to ``pcl::KdTreeFLANN``, except OneAPI KdTree can search the entire point cloud
in a single call, while ``pcl::KdTreeFLANN`` performs a search for one point at a time. The OneAPI
version returns a two-dimensional vector of indices and distances for the entire point cloud search
or single dimensional vector of indices, distances, splits for entire point cloud search.
Both ``nearestKSearch`` and ``radiusSearch`` are supported.

OneAPI includes an additional higher-performance fixed-radius search, which performs a radius search
from a hash table. Unlike ``pcl::KdTreeFLANN``'s radius search, which supports searching with different
radius values once a KdTree has been built, the fixed-radius search requires specifying a radius to
build the hash table. The hash table can only search for a fixed radius. The time required to build
a fixed-radius hash table is much shorter than that of FLANN KdTree. Another difference is that only
FLANN KdTree supports returning K elements from radius search, while fixed-radius search always
returns all elements. For the same radius value, the results of both FLANN and fixed-radius search
should match.

This document will not describe KdTree in detail, and please refer to original `kdtree_search <https://pointclouds.org/documentation/tutorials/kdtree_search.html>`__ for more detail KdTree.

.. note::

  This tutorial is applicable for execution both within inside and outside a |docker| image. It assumes that the
  *pcl-oneapi-tutorials* |deb_pack| is installed, and the user has copied the *tutorial*
  directory from */opt/intel/pcl/oneapi/tutorials/* to a user-writable directory.

#. Prepare the environment:

   .. code-block::

      cd <path-to-oneapi-tutorials>/kdtree


#. ``oneapi_kdtree.cpp`` should be in the directory with following content:

   .. literalinclude:: ../../../../sources/kdtree/oneapi_kdtree.cpp
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

      ./oneapi_kdtree

#. Expected results example:

   .. code-block::

      K=5 neighbors from (911.933,321.699,128.681)
        870.884 350.103 160.644 (squared distance: 3513.43)
        856.565 374.562 132.514 (squared distance: 5874.84)
        960.284 267.917 173.756 (squared distance: 7262)
        987.681 359.434 104.805 (squared distance: 7731.77)
        929.787 396.96 84.1415 (squared distance: 7966.85)
      K=5 neighbors from (39.0119,923.789,113.278)
        36.4024 943.423 84.1814 (squared distance: 1238.91)
        68.2891 927.112 150.885 (squared distance: 2282.5)
        79.0735 887.262 63.1519 (squared distance: 5451.72)
        119.306 1021.4 127.402 (squared distance: 16175.4)
        116.103 800.647 145.881 (squared distance: 22169.9)
      K=5 neighbors from (542.853,566.777,4.23339)
        481.511 597.7 27.2575 (squared distance: 5249.24)
        570.652 585.804 69.9711 (squared distance: 5456.25)
        574.454 498.665 37.4542 (squared distance: 6741.42)
        569.49 480.913 6.70625 (squared distance: 8088.2)
        649.963 597.5 25.601 (squared distance: 12872.9)
      Kdtree Radius Search Radius=100 neighbors from (911.933,321.699,128.681)
        870.884 350.103 160.644 (squared distance: 3513.43)
        856.565 374.562 132.514 (squared distance: 5874.84)
        960.284 267.917 173.756 (squared distance: 7262)
        987.681 359.434 104.805 (squared distance: 7731.77)
        929.787 396.96 84.1415 (squared distance: 7966.85)
        967.947 352.763 64.8979 (squared distance: 8170.85)
        974.103 248.606 116.676 (squared distance: 9351.69)
        842.968 389.302 109.632 (squared distance: 9689.34)
      Kdtree Radius Search Radius=100 neighbors from (39.0119,923.789,113.278)
        36.4024 943.423 84.1814 (squared distance: 1238.91)
        68.2891 927.112 150.885 (squared distance: 2282.5)
        79.0735 887.262 63.1519 (squared distance: 5451.72)
      Kdtree Radius Search Radius=100 neighbors from (542.853,566.777,4.23339)
        481.511 597.7 27.2575 (squared distance: 5249.24)
        570.652 585.804 69.9711 (squared distance: 5456.25)
        574.454 498.665 37.4542 (squared distance: 6741.42)
        569.49 480.913 6.70625 (squared distance: 8088.2)
      Fixed Radius Search Radius=100 neighbors from (911.933,321.699,128.681)
        870.884 350.103 160.644 (squared distance: 3513.43)
        856.565 374.562 132.514 (squared distance: 5874.84)
        960.284 267.917 173.756 (squared distance: 7262)
        987.681 359.434 104.805 (squared distance: 7731.77)
        929.787 396.96 84.1415 (squared distance: 7966.85)
        967.947 352.763 64.8979 (squared distance: 8170.85)
        974.103 248.606 116.676 (squared distance: 9351.69)
        842.968 389.302 109.632 (squared distance: 9689.34)
      Fixed Radius Search Radius=100 neighbors from (39.0119,923.789,113.278)
        36.4024 943.423 84.1814 (squared distance: 1238.91)
        68.2891 927.112 150.885 (squared distance: 2282.49)
        79.0735 887.262 63.1519 (squared distance: 5451.72)
      Fixed Radius Search Radius=100 neighbors from (542.853,566.777,4.23339)
        481.511 597.7 27.2575 (squared distance: 5249.24)
        570.652 585.804 69.9711 (squared distance: 5456.25)
        574.454 498.665 37.4542 (squared distance: 6741.42)
        569.49 480.913 6.70625 (squared distance: 8088.2)


Code Explanation
-----------------

Compare to original version, the OneAPI version requires to use the OneAPI KdTree header.

.. literalinclude:: ../../../../sources/kdtree/oneapi_kdtree.cpp
   :language: cpp
   :lines: 3
   :dedent:

The following code first seeds the 'rand()' function with the system time and then creates and fills
a PointCloud with random data. Another set of search points with random coordinates is created as
well. The objective here is to perform a search for 3 coordinates using a single call.

.. literalinclude:: ../../../../sources/kdtree/oneapi_kdtree.cpp
   :language: cpp
   :lines: 12-42
   :dedent:

This section of code initializes the KdTree object and sets the randomly created cloud as the input.

.. literalinclude:: ../../../../sources/kdtree/oneapi_kdtree.cpp
   :language: cpp
   :lines: 44-45
   :dedent:

An integer variable is created (set to 5), along with two two-dimensional vectors designed to store
the K nearest neighbors from the search.

.. literalinclude:: ../../../../sources/kdtree/oneapi_kdtree.cpp
   :language: cpp
   :lines: 47-53
   :dedent:

Assuming that the KdTree returns more than 0 closest neighbors, it proceeds to print out the
locations of all 5 closest neighbors to the random ``searchPoints``, which have been stored in the
previously created vectors.

.. literalinclude:: ../../../../sources/kdtree/oneapi_kdtree.cpp
   :language: cpp
   :lines: 55-67
   :dedent:

The code then demonstrates the process of finding all neighbors to the given ``searchPoints`` within a
specified radius. Two vectors are created to store information about these neighbors.

.. literalinclude:: ../../../../sources/kdtree/oneapi_kdtree.cpp
   :language: cpp
   :lines: 69-75
   :dedent:

Similar to the previous scenario, if the KdTree returns more than 0 neighbors within the specified
radius, it prints out the coordinates of these points, which have been stored in the vectors.

.. literalinclude:: ../../../../sources/kdtree/oneapi_kdtree.cpp
   :language: cpp
   :lines: 77-89
   :dedent:

Additionally, a fixed radius search method is provided through a hash table. As this is a fixed
radius search, it is necessary to provide the radius to build the table.

.. literalinclude:: ../../../../sources/kdtree/oneapi_kdtree.cpp
   :language: cpp
   :lines: 91-98
   :dedent:

The fixed radius search returns a one-dimensional vector containing both indices and squared
distances for the neighbors. To access the respective ``searchPoints``, the returned split vector is
used. The example below demonstrates how to access each ``searchPoint``.

.. literalinclude:: ../../../../sources/kdtree/oneapi_kdtree.cpp
   :language: cpp
   :lines: 100-119
   :dedent:
