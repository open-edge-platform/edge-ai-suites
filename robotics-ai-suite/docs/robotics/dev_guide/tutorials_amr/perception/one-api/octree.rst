.. _oneapi_octree_search:

Spatial Partitioning and Search Operations with Octrees
=============================================================================

An octree is a tree data structure in which each internal node has exactly eight children. Octrees are most often used to partition a three-dimensional space by recursively subdividing it into eight octants. Octrees are the three-dimensional analog of quadtrees. The word is derived from oct (Greek root meaning "eight") + tree. Octrees are often used in 3D graphic and 3D game engines.

In this tutorial we will learn how to use the octree for spatial partitioning and neighbor search within the point cloud data. This tutorial covers the process of performing "Neighbors within Radius Search", "Approximate Nearest Neighbor (ANN) Search" and "K-Nearest Neighbors (KNN) Search".

.. note::

  This tutorial can be run both inside and outside a |docker| image. We assume that the
  *pcl-oneapi-tutorials* |deb_pack| has been installed, and the user has copied the *tutorial*
  directory from */opt/intel/pcl/oneapi/tutorials/* to a user-writable directory.

#. Prepare the environment:

   .. code-block::

      cd <path-to-oneapi-tutorials>/octree


#. ``oneapi_octree_search.cpp`` should be in the directory with following content:

   .. literalinclude:: ../../../../sources/octree/oneapi_octree_search.cpp
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

      ./oneapi_octree_search

#. Expected results example:

  The search only finds the first five neighbors (as specified by
  ``max_answers``), so a different radius finds different points.

   .. code-block::

      Neighbors within shared radius search at (671.675 733.78 466.178) with radius=34.1333
        660.296 725.957 439.677 (distance: 29.8829)
        665.768 721.884 442.919 (distance: 26.7846)
        683.988 714.608 445.164 (distance: 30.9962)
        677.927 725.08 446.531 (distance: 22.3788)
        695.066 723.509 445.762 (distance: 32.7028)
      Neighbors within individual radius search at (671.675 733.78 466.178) with radius=19.3623
        672.71 736.679 447.835 (distance: 18.6)
        664.46 731.504 452.074 (distance: 16.0048)
        671.238 725.881 461.408 (distance: 9.23819)
        667.707 718.527 466.622 (distance: 15.7669)
        654.552 733.636 467.795 (distance: 17.1993)
      Neighbors within indices radius search at (671.675 733.78 466.178) with radius=34.1333
        660.296 725.957 439.677 (distance: 29.8829)
        665.768 721.884 442.919 (distance: 26.7846)
        683.988 714.608 445.164 (distance: 30.9962)
        677.927 725.08 446.531 (distance: 22.3788)
        695.066 723.509 445.762 (distance: 32.7028)


Code Explanation
--------------------

Generate point cloud data, queries, radiuses, indices with a random number.

.. literalinclude:: ../../../../sources/octree/oneapi_octree_search.cpp
   :language: cpp
   :lines: 33-57
   :dedent:

Create and build the |oneapi| point cloud; then upload the queries and
   radiuses to a |oneapi| device.

.. literalinclude:: ../../../../sources/octree/oneapi_octree_search.cpp
   :language: cpp
   :lines: 59-72
   :dedent:

Create output buffers where we can download output from the |oneapi| device.

.. literalinclude:: ../../../../sources/octree/oneapi_octree_search.cpp
   :language: cpp
   :lines: 74-81
   :dedent:

The fist radius search method is "search with shared radius". In this search
method, all queries use the same radius to find the neighbors.

.. literalinclude:: ../../../../sources/octree/oneapi_octree_search.cpp
   :language: cpp
   :lines: 83-87
   :dedent:

The second radius search method is "search with individual radius". In this
search method, each query uses its own specific radius to find the neighbors.

.. literalinclude:: ../../../../sources/octree/oneapi_octree_search.cpp
   :language: cpp
   :lines: 86-87
   :dedent:

The third radius search method is "search with shared radius using indices". In
this search method, all queries use the same radius, and indices specify the
queries.

.. literalinclude:: ../../../../sources/octree/oneapi_octree_search.cpp
   :language: cpp
   :lines: 89-93
   :dedent:

Perform ANN search.

.. literalinclude:: ../../../../sources/octree/oneapi_octree_search.cpp
   :language: cpp
   :lines: 95-98
   :dedent:

Perform KNN search.

.. literalinclude:: ../../../../sources/octree/oneapi_octree_search.cpp
   :language: cpp
   :lines: 100-103
   :dedent:

Download the search results from the |oneapi| device. The size vector contains
the size of found neighbors for each query. The downloaded_buffer vector
contains the index of all found neighbors for each query.

.. literalinclude:: ../../../../sources/octree/oneapi_octree_search.cpp
   :language: cpp
   :lines: 105-116
   :dedent:

Print the query, radius, and found neighbors to verify that the result is
correct.

.. literalinclude:: ../../../../sources/octree/oneapi_octree_search.cpp
   :language: cpp
   :lines: 118-174
   :dedent:
