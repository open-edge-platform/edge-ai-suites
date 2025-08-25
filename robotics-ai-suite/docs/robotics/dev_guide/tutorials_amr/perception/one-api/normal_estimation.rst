.. _oneapi_normal_estimation:

Estimating Surface Normals in a PointCloud
==================================================

In this tutorial, we will learn how to obtain the surface normals of each point in the cloud.

.. note::

  This tutorial is applicable for execution for both within inside and outside a |docker| image. It assumes that the
  *pcl-oneapi-tutorials* |deb_pack| is installed, and the user has copied the *tutorial*
  directory from */opt/intel/pcl/oneapi/tutorials/* to a user-writable directory.

#. Prepare the environment:

   .. code-block::

      cd <path-to-oneapi-tutorials>/normal_estimation


#. ``oneapi_normal_estimation.cpp`` should be in the directory with following content:

   .. literalinclude:: ../../../../sources/normal_estimation/oneapi_normal_estimation.cpp
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

      ./oneapi_normal_estimation

#. Expected results example:

   .. code-block::

      normals_knn.size (): 397
      normals_radius.size (): 397



Code Explanation
------------------

The example PCD is initially loaded into a PointCloud<PointXYZ>.

.. literalinclude:: ../../../../sources/normal_estimation/oneapi_normal_estimation.cpp
   :language: cpp
   :lines: 15-23
   :dedent:

This tutorial includes two normal estimation processes: KNN search and Radius search. The initial
step involves adjusting the parameters for normal estimation in the KNN search.

.. literalinclude:: ../../../../sources/normal_estimation/oneapi_normal_estimation.cpp
   :language: cpp
   :lines: 25-29
   :dedent:

Normal estimation is then executed.

.. literalinclude:: ../../../../sources/normal_estimation/oneapi_normal_estimation.cpp
   :language: cpp
   :lines: 32-33
   :dedent:

The parameters for normal estimation are modified for the radius search.

.. literalinclude:: ../../../../sources/normal_estimation/oneapi_normal_estimation.cpp
   :language: cpp
   :lines: 37-41
   :dedent:

Normal estimation is performed once more.

.. literalinclude:: ../../../../sources/normal_estimation/oneapi_normal_estimation.cpp
   :language: cpp
   :lines: 43-45
   :dedent:
