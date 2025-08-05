.. _oneapi_registration:

|l_oneapi|\'s Iterative Closest Point (ICP)
=============================================================================

The standard Iterative Closest Point (ICP) has been optimized using |l_oneapi|.
Joint ICP and Generalized ICP are not currently optimized with |l_oneapi|. This tutorial
covers the standard ICP.

Iterative Closest Point
-----------------------

Iterative closest point (ICP) is an algorithm utilized to minimize the
difference between two point clouds.

The ICP steps are:

1. For each point in the source point cloud, match the closest point in the
   reference/target point cloud.
2. Estimate the combination of rotation and translation using a
   root mean square point-to-point distance metric minimization technique which
   will best align each source point to its match found in the previous step.
3. Apply the obtained transformation to source point cloud.
4. Iterate (re-associate the points, and so on).

For details regarding the PCL Registration module and its internal algorithmic
details, please refer to the `registration_api
<https://github.com/PointCloudLibrary/pcl/blob/master/doc/tutorials/content/registration_api.rst>`__
for details.

.. note::

  This tutorial is applicable for execution both within inside and outside a |docker| image. It assumes that the
  *pcl-oneapi-tutorials* |deb_pack| is installed, and the user has copied the *tutorial*
  directory from */opt/intel/pcl/oneapi/tutorials/* to a user-writable directory.

#. Prepare the environment:

   .. code-block::

      cd <path-to-oneapi-tutorials>/registration

#. ``oneapi_icp_example.cpp`` should be in the directory with following content:

   .. literalinclude:: ../../../../sources/registration/oneapi_icp_example.cpp
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

      ./oneapi_icp_example

#. Expected results example:

   .. code-block::

      Transform Matrix:
      0.998899   0.0107221   0.0457259   0.0790768
      -0.00950837    0.999602  -0.0266773   0.0252976
      -0.0459936    0.026213    0.998599   0.0677631
              0           0           0           1


Code Explanation
--------------------

Define two input point Clouds (src, tgt), declare the output point cloud, and
load the test data from GitHub*.

.. literalinclude:: ../../../../sources/registration/oneapi_icp_example.cpp
   :language: cpp
   :lines: 21-29
   :dedent:

Declare oneapi ICP, and set the input configuration parameters.

.. literalinclude:: ../../../../sources/registration/oneapi_icp_example.cpp
   :language: cpp
   :lines: 32-36
   :dedent:

Set the two input point clouds for the ICP module, and call the method to align
the two point clouds. The align method populates the output point cloud, passed
as a parameter, with the src point cloud transformed using the computed
transformation matrix.

.. literalinclude:: ../../../../sources/registration/oneapi_icp_example.cpp
   :language: cpp
   :lines: 38-42
   :dedent:

Get the computed matrix transformation, print it, and save the transformed point
cloud.

.. literalinclude:: ../../../../sources/registration/oneapi_icp_example.cpp
   :language: cpp
   :lines: 44-46
   :dedent:
