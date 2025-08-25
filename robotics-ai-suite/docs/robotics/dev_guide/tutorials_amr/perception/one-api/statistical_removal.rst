.. _oneapi_statistical_outlier_removal:

Removing Outliers Using a StatisticalOutlierRemoval Filter
===============================================================

This tutorial demonstrates the process of eliminating noisy measurements, e.g. outliers,
from a point cloud data set using statistical analysis techniques.  This is the |oneapi| optimization
version of ``pcl::StatisticalOutlierRemoval``.

For more info of ``pcl::StatusticalOutlierRemoval`` filter, refer to `this page.
<https://pointclouds.org/documentation/tutorials/statistical_outlier.html>`_

.. note::

  This tutorial is applicable for execution both inside and outside a |docker| image. It assumes that the
  *pcl-oneapi-tutorials* |deb_pack| is installed, and the user has copied the *tutorial*
  directory from */opt/intel/pcl/oneapi/tutorials/* to a user-writable directory.

#. Prepare the environment:

   .. code-block::

      cd <path-to-oneapi-tutorials>/statistical_outlier_removal


#. ``oneapi_statistical_outlier_removal.cpp`` should be in the directory with following content:

   .. literalinclude:: ../../../../sources/statistical_outlier_removal/oneapi_statistical_outlier_removal.cpp
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

      ./oneapi_statistical_outlier_removal


#. Expected results example:

   .. code-block::

      Cloud before filtering:
      header: seq: 0 stamp: 0 frame_id:

      points[]: 460400
      width: 460400
      height: 1
      is_dense: 1
      sensor origin (xyz): [0, 0, 0] / orientation (xyzw): [0, 0, 0, 1]

      Cloud after filtering:
      header: seq: 0 stamp: 0 frame_id:

      points[]: 451410
      width: 451410
      height: 1
      is_dense: 1
      sensor origin (xyz): [0, 0, 0] / orientation (xyzw): [0, 0, 0, 1]


Code Explanation
----------------

Now, let's break down the code piece by piece.

The following lines of code will read the point cloud data from disk.

.. literalinclude:: ../../../../sources/statistical_outlier_removal/oneapi_statistical_outlier_removal.cpp
   :language: cpp
   :lines: 14-17
   :dedent:

Then, a *pcl::StatisticalOutlierRemoval* filter is created. The number of neighbors to analyze for each point is set to 50, and the standard deviation
multiplier threshold to 1. What this means is that all points that have distance larger than 1 standard deviation of the mean distance to the query point will be
marked as outliers and removed. The output is computed and stored in *oneapi_cloud_filtered*.

.. literalinclude:: ../../../../sources/statistical_outlier_removal/oneapi_statistical_outlier_removal.cpp
   :language: cpp
   :lines: 24-29
   :dedent:

The remaining data (inliers) is written to disk for later inspection.

.. literalinclude:: ../../../../sources/statistical_outlier_removal/oneapi_statistical_outlier_removal.cpp
   :language: cpp
   :lines: 34-34
   :dedent:

Then, the filter is called with the same parameters, but with the output negated, to obtain the outliers (e.g., the points that were filtered).

.. literalinclude:: ../../../../sources/statistical_outlier_removal/oneapi_statistical_outlier_removal.cpp
   :language: cpp
   :lines: 37-38
   :dedent:

And the data is written back to disk.

.. literalinclude:: ../../../../sources/statistical_outlier_removal/oneapi_statistical_outlier_removal.cpp
   :language: cpp
   :lines: 39
   :dedent:
