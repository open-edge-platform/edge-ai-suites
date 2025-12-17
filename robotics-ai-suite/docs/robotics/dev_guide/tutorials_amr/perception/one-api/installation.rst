.. _oneapi-installation:

Overview and Installation
===========================

Overview
--------

Intel PCL optimization is accomplished using Intel® oneAPI Base Toolkit, which
comprises components such as the oneAPI DPC++ Compiler, OpenMP and oneAPI Threading Building
Blocks (``oneTBB``).  This optimization maximizes performance by fully utilizing the hardware's
available resources.

Only selected PCL modules listed in this `modules`_ table are available in oneAPI
version.  Most of the optimized module closely follow original PCL modules APIs except with
additional oneAPI namespace.  For example

PCL KdTree class

   .. code-block::

    pcl::KdTreeFLANN<pcl::PointXYZ> kdtree;
    kdtree.setInputCloud (cloud.makeShared())

oneAPI PCL KdTree class

   .. code-block::

    pcl::oneapi::KdTreeFLANN<pcl::PointXYZ> kdtree;
    kdtree.setInputCloud (cloud.makeShared())

**Below are PCL modules optimized through** Intel® oneAPI Base Toolkit

.. _modules:
.. list-table:: Optimized oneAPI PCL modules
    :header-rows: 1
    :widths: 7 20 7
    :stub-columns: 0

    *  - Modules
       - Class
       - Supported HW

    *  - filters
       - :doc:`PassThrough <passthrough>`
       - CPU/GPU
    *  -
       - :doc:`StatisticalOutlierRemoval <statistical_removal>`
       - CPU/GPU
    *  -
       - :doc:`VoxelGrid <voxel_grid>`
       - CPU/GPU
    *  - features
       - :doc:`NormalEstimation <normal_estimation>`
       - CPU/GPU
    *  - KdTree
       - :doc:`KdTreeFLANN <kdtree>` *(radiusSearch, nearestKSearch)*
       - CPU/GPU
    *  - octree
       - :doc:`Octree <octree>` *(radiusSearch, nearestKSearchBatch, approxNearestSearch)*
       - CPU/GPU
    *  - registration
       - :doc:`IterativeClosestPoint <registration>` (ICP)
       - CPU/GPU
    *  -
       - IterativeClosestPointWithNormals
       - CPU/GPU
    *  -
       - :doc:`SampleConsensusInitialAlignment <scia>`
       - CPU/GPU
    *  - segmentation
       - :doc:`SACSegmentation <segmentation>`
       - CPU/GPU
    *  - sample_consensus
       - :doc:`RandomSampleConsensus <sample_consensus>`
       - CPU/GPU
    *  -
       - :doc:`SampleConsensusModelPlane <sample_consensus>`
       - CPU/GPU
    *  - surface
       - :doc:`MovingLeastSquares <mls>`
       - CPU/GPU
    *  -
       - :doc:`GreedyProjectionTriangulation <greedy_projection>`
       - CPU

Supported Hardware
------------------

**CPUs:**

Systems based on Intel® 64 architectures below are supported

* Intel® Core™ processor family

* Intel® Xeon® processor family

**GPUs:**

* `Integrated Processor Graphics site <https://www.intel.com/content/www/us/en/developer/articles/guide/intel-graphics-developers-guides.html>`__ Skylake or higher

Supported Operating System
--------------------------

* Ubuntu 22.04 LTS
* Microsoft Windows 10/11

Prerequisites
-------------

Complete the :doc:`../../../../gsg_robot/index` before continuing.

PCL oneAPI Installation
-------------------------
The PCL oneAPI version depends on the oneAPI runtime library.  By installing the ``libpcl-oneapi`` Debian
package, it will install all dependencies include ``libpcl`` and pcl dependency libraries,  oneAPI runtime library and GPU runtime
library.

1. Install PCL oneAPI version

   .. code-block::

     sudo apt install libpcl-oneapi

2. To develop with the PCL oneAPI™ library or build PCL oneAPI™ tutorials, you need the Intel® oneAPI Base Toolkit. To install Intel® oneAPI Base Toolkit,

  a. For Docker environment:

   .. code-block::

     sudo apt install intel-oneapi-compiler-dpcpp-cpp-2024.0 intel-oneapi-dpcpp-ct-2024.0

  b. For host environment, refer to the product page `Get the Intel® oneAPI Base Toolkit <https://www.intel.com/content/www/us/en/developer/tools/oneapi/base-toolkit-download.html>`__
     to download and install. Choose Linux OS, and then APT Package Manager.  Follow the instructions to set up the APT repository for first-time users, then proceed with the apt command.

   .. code-block::

     sudo apt install intel-oneapi-compiler-dpcpp-cpp-2024.0 intel-oneapi-dpcpp-ct-2024.0


3. Install the PCL oneAPI tutorials.  Refer to the individual PCL `modules`_ table for more information

   .. code-block::

     sudo apt install pcl-oneapi-tutorials

Boost Patching for Compatibility
--------------------------------

The following changes to Boost are required to ensure compatibility with modern C++ standards (C++17 and later) if Boost version is less than 1.83:

**File: /usr/include/boost/numeric/conversion/detail/int_float_mixture.hpp**

.. code-block:: diff

   -#include "boost/mpl/integral_c.hpp"
   +#include "boost/type_traits/integral_constant.hpp"
   
   -typedef mpl::integral_c<int_float_mixture_enum, integral_to_integral> int2int_c ;
   -typedef mpl::integral_c<int_float_mixture_enum, integral_to_float> int2float_c ;
   -typedef mpl::integral_c<int_float_mixture_enum, float_to_integral> float2int_c ;
   -typedef mpl::integral_c<int_float_mixture_enum, float_to_float> float2float_c ;
   + typedef boost::integral_constant<int_float_mixture_enum, integral_to_integral> int2int_c ;
   + typedef boost::integral_constant<int_float_mixture_enum, integral_to_float> int2float_c ;
   + typedef boost::integral_constant<int_float_mixture_enum, float_to_integral> float2int_c ;
   + typedef boost::integral_constant<int_float_mixture_enum, float_to_float> float2float_c ;

**File: /usr/include/boost/numeric/conversion/detail/udt_builtin_mixture.hpp**

.. code-block:: diff

   -#include "boost/mpl/integral_c.hpp"
   +#include "boost/type_traits/integral_constant.hpp"
   
   -typedef mpl::integral_c<udt_builtin_mixture_enum, builtin_to_builtin> builtin2builtin_c ;
   -typedef mpl::integral_c<udt_builtin_mixture_enum, builtin_to_udt> builtin2udt_c ;
   -typedef mpl::integral_c<udt_builtin_mixture_enum, udt_to_builtin> udt2builtin_c ;
   -typedef mpl::integral_c<udt_builtin_mixture_enum, udt_to_udt> udt2udt_c ;
   + typedef boost::integral_constant<udt_builtin_mixture_enum, builtin_to_builtin> builtin2builtin_c ;
   + typedef boost::integral_constant<udt_builtin_mixture_enum, builtin_to_udt> builtin2udt_c ;
   + typedef boost::integral_constant<udt_builtin_mixture_enum, udt_to_builtin> udt2builtin_c ;
   + typedef boost::integral_constant<udt_builtin_mixture_enum, udt_to_udt> udt2udt_c ;

**File: /usr/include/boost/numeric/conversion/detail/sign_mixture.hpp**

.. code-block:: diff

   -#include "boost/mpl/integral_c.hpp"
   +#include "boost/type_traits/integral_constant.hpp"
   
   -typedef mpl::integral_c<sign_mixture_enum, unsigned_to_unsigned> unsig2unsig_c ;
   -typedef mpl::integral_c<sign_mixture_enum, signed_to_signed> sig2sig_c ;
   -typedef mpl::integral_c<sign_mixture_enum, signed_to_unsigned> sig2unsig_c ;
   -typedef mpl::integral_c<sign_mixture_enum, unsigned_to_signed> unsig2sig_c ;
   + typedef boost::integral_constant<sign_mixture_enum, unsigned_to_unsigned> unsig2unsig_c ;
   + typedef boost::integral_constant<sign_mixture_enum, signed_to_signed> sig2sig_c ;
   + typedef boost::integral_constant<sign_mixture_enum, signed_to_unsigned> sig2unsig_c ;
   + typedef boost::integral_constant<sign_mixture_enum, unsigned_to_signed> unsig2sig_c ;

**File: /usr/include/boost/mpl/aux_/integral_wrapper.hpp**

.. code-block:: diff

   - #if BOOST_WORKAROUND(__EDG_VERSION__, <= 243)
   + #if BOOST_WORKAROUND(__EDG_VERSION__, <= 243) || __cplusplus >= 201703L

These changes replace deprecated ``mpl::integral_c`` with ``boost::integral_constant`` and add C++17 compatibility to the integral wrapper workaround.


Runtime Device Selection
------------------------
oneAPI runtime library will choose a default device for a platform, either CPU or GPU.  Currently,
the oneAPI version of PCL modules does not support the API to switch between different devices.  To switch to
device from default device, the only option is to select through oneAPI environment variable.

1.  To find devices supported for given platform

   a. Initialize oneAPI environment variable.


   .. code-block::

    source /opt/intel/oneapi/setvars.sh

   b. Find all devices supported

   .. code-block::

    sycl-ls

   | Example of sycl-ls output

   .. code-block::

    [opencl:cpu:0] Intel(R) OpenCL, 12th Gen Intel(R) Core(TM) i7-1270PE 3.0 [2023.16.6.0.22_223734]
    [opencl:gpu:1] Intel(R) OpenCL Graphics, Intel(R) Graphics [0x46a6] 3.0 [23.22.26516.18]
    [opencl:acc:2] Intel(R) FPGA Emulation Platform for OpenCL(TM), Intel(R) FPGA Emulation Device 1.2 [2023.16.6.0.22_223734]
    [opencl:cpu:3] Intel(R) OpenCL, 12th Gen Intel(R) Core(TM) i7-1270PE 3.0 [2023.16.6.0.22_223734]
    [ext_oneapi_level_zero:gpu:0] Intel(R) Level-Zero, Intel(R) Graphics [0x46a6] 1.3 [1.3.26516]



2. Select device for computation.  For example

   a. Select CPU device

   .. code-block::

    export ONEAPI_DEVICE_SELECTOR=opencl:cpu
    sycl-ls


   .. code-block::

    Warning: ONEAPI_DEVICE_SELECTOR environment variable is set to opencl:cpu.
    To see the correct device id, please unset ONEAPI_DEVICE_SELECTOR.

    [opencl:cpu:0] Intel(R) OpenCL, 12th Gen Intel(R) Core(TM) i7-1270PE 3.0 [2023.16.6.0.22_223734]
    [opencl:cpu:1] Intel(R) OpenCL, 12th Gen Intel(R) Core(TM) i7-1270PE 3.0 [2023.16.6.0.22_223734]



   b. Select GPU device

   .. code-block::

    export ONEAPI_DEVICE_SELECTOR=level_zero:gpu
    sycl-ls

   .. code-block::

    Warning: ONEAPI_DEVICE_SELECTOR environment variable is set to level_zero:gpu.
    To see the correct device id, please unset ONEAPI_DEVICE_SELECTOR.

    [ext_oneapi_level_zero:gpu:0] Intel(R) Level-Zero, Intel(R) Graphics [0x46a6] 1.3 [1.3.26516]

3.  For more information of SYCL environment variables supported by oneAPI, refer to `this page <https://github.com/intel/llvm/blob/sycl/sycl/doc/EnvironmentVariables.md>`__ for all supported environment variables.


JIT Limitation
--------------

Most oneAPI™ PCL modules are implemented with the Intel® oneAPI™ DPC++ Compiler.
The Intel® oneAPI™ DPC++ Compiler converts a DPC++ program into an intermediate
language called SPIR-V (Standard Portable Intermediate Representation). The
SPIR-V code is stored in the binary produced by the compilation process. The
SPIR-V code has the advantage that it can be run on any hardware platform by
translating the SPIR-V code into the assembly code of the given platform at
runtime. This process of translating the intermediate code present in the binary
is called Just-In-Time (JIT) compilation. Since JIT compilation happens at the
beginning of the execution of the first offloaded kernel, the performance is
impacted. This issue can be mitigated by setting the system environment variable
to cache and reuse JIT-compiled binaries.

#. Set the system environment variable to cache and reuse JIT-compiled binaries.

   .. code-block::

      export SYCL_CACHE_PERSISTENT=1

#. Set the environment variable permanently.

   .. code-block::

      echo "export SYCL_CACHE_PERSISTENT=1" >> ~/.bashrc
      source ~/.bashrc

#. Execute the program once to generate the JIT-compiled binaries. Subsequent
   executions will reuse the cached JIT-compiled binaries.


.. note::

   For an accurate PCL optimization performance number, set this system
   environment variable, and execute the program once to generate and cache the JIT-compiled binaries.
