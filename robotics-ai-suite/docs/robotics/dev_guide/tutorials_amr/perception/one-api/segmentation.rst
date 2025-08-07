.. _oneapi_segmentation:

Plane Model Segmentation
=============================================================================

In this tutorial, we will explore the process of simple plane segmentation, extracting points within a point cloud that contribute to a plane model.

.. note::

  This tutorial is applicable for execution both within inside and outside a |docker| image. It assumes that the
  *pcl-oneapi-tutorials* |deb_pack| is installed, and the user has copied the *tutorial*
  directory from */opt/intel/pcl/oneapi/tutorials/* to a user-writable directory.

#. Prepare the environment:

   .. code-block::

      cd <path-to-oneapi-tutorials>/segmentation


#. ``oneapi_segmentation.cpp`` should be in the directory with following content:

   .. literalinclude:: ../../../../sources/segmentation/oneapi_segmentation.cpp
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

      ./oneapi_segmentation

#. Expected results example:

   .. code-block::

      input cloud size   : 307200
      inliers size       : 25332
      model coefficients : -0.176599, -1.87228, -1.08408, 1


Code Explanation
--------------------

Load the test data from GitHub* into a PointCloud<PointXYZ>.

.. literalinclude:: ../../../../sources/segmentation/oneapi_segmentation.cpp
   :language: cpp
   :lines: 11-12
   :dedent:

Create the oneapi_segmentation object.

.. literalinclude:: ../../../../sources/segmentation/oneapi_segmentation.cpp
   :language: cpp
   :lines: 23
   :dedent:

Configure the oneapi_segmentation class.

.. literalinclude:: ../../../../sources/segmentation/oneapi_segmentation.cpp
   :language: cpp
   :lines: 26-34
   :dedent:

Set to true if a coefficient refinement is required.

.. literalinclude:: ../../../../sources/segmentation/oneapi_segmentation.cpp
   :language: cpp
   :lines: 31
   :dedent:

Set the algorithm method and model type.

.. literalinclude:: ../../../../sources/segmentation/oneapi_segmentation.cpp
   :language: cpp
   :lines: 33-34
   :dedent:

Declare output parameters for getting inliers and model coefficients.

.. literalinclude:: ../../../../sources/segmentation/oneapi_segmentation.cpp
   :language: cpp
   :lines: 37-38
   :dedent:

Get inliers and model coefficients by calling the segment() API.

.. literalinclude:: ../../../../sources/segmentation/oneapi_segmentation.cpp
   :language: cpp
   :lines: 41
   :dedent:

Result (output log):

.. literalinclude:: ../../../../sources/segmentation/oneapi_segmentation.cpp
   :language: cpp
   :lines: 43-45
   :dedent:
