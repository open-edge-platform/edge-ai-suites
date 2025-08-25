.. _oneapi_scia:

Using SampleConsensusInitialAligment (SCIA) to Initial Align Two Point Clouds
===============================================================================

In this tutorial, we will learn how to initial align two point clouds, using SCIA, provided with the transformation 4x4 matrix.

.. note::

  This tutorial is applicable for execution for both within inside and outside a |docker| image. It assumes that the
  *pcl-oneapi-tutorials* |deb_pack| is installed, and the user has copied the *tutorial*
  directory from */opt/intel/pcl/oneapi/tutorials/* to a user-writable directory.

#. Prepare the environment:

   .. code-block::

      cd <path-to-oneapi-tutorials>/sample_consensus_initial_alignment


#. ``oneapi_scia.cpp`` should be in the directory with following content:

   .. literalinclude:: ../../../../sources/sample_consensus_initial_alignment/oneapi_scia.cpp
      :language: cpp
      :linenos:


#. Source the |l_oneapi| environment:

   .. code-block::

      source /opt/intel/oneapi/setvars.sh


#. Build the code:

   .. code-block::

      mkdir build && cd build
      cmake ../
      make -j

#. Run the binary:

   .. code-block::

      ./oneapi_scia

#. Expected results example:

   .. code-block::

      [oneapi SCIA] Transformation Matrix 4x4 = 
       0.268113 -0.734448 -0.623458  0.289958
       0.748389 -0.248733  0.614853 -0.208532
      -0.606653  -0.63144  0.482965  0.229585
              0         0         0         1

Code Explanation
------------------

Load ``source/target/fpfh_source/fpfh_target`` PCD file

.. literalinclude:: ../../../../sources/sample_consensus_initial_alignment/oneapi_scia.cpp
   :language: cpp
   :lines: 20-29
   :dedent:

Load the example ``source/target/fpfh_source/fpfh_target`` PCD into a ``PointCloud<PointXYZ/FPFHSignature33>``.

.. literalinclude:: ../../../../sources/sample_consensus_initial_alignment/oneapi_scia.cpp
   :language: cpp
   :lines: 30-39
   :dedent:

Start to compute the model.

.. literalinclude:: ../../../../sources/sample_consensus_initial_alignment/oneapi_scia.cpp
   :language: cpp
   :lines: 41-58
   :dedent:

Result (output log).

.. literalinclude:: ../../../../sources/sample_consensus_initial_alignment/oneapi_scia.cpp
   :language: cpp
   :lines: 60-61
   :dedent:
