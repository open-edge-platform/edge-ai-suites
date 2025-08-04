.. _oneapi-troubleshooting:

Optimized PCL Limitation and Troubleshooting
============================================

Limitation
----------

This optimized PCL release does not support acceleration for CPU device for

* 12th generation of |atom| processors, known as codename 'Alder Lake-N'.


Troubleshooting
---------------

If the executable produces a segmentation fault (core dumped) when running with a GPU device or
if the GPU device is not listed in ``sycl-ls`` like below

.. code-block::

   source /opt/intel/oneapi/setvars.sh

   sycl-ls
   [opencl:0] ACC : Intel(R) FPGA Emulation Platform for OpenCL(TM) 1.2 [2021.13.11.0.23_160000]
   [opencl:0] CPU : Intel(R) OpenCL 3.0 [2021.13.11.0.23_160000]
   [opencl:0] GPU : Intel(R) OpenCL HD Graphics 3.0 [22.17.23034]
   [level_zero:0] GPU : Intel(R) Level-Zero 1.3 [1.3.23034]
   [host:0] HOST: SYCL host platform 1.2 [1.2]

There are two possibilities.  The |intel| processor does not have integrated GPU or the user does not have the correct group permissions to access to GPU device.  Add the user to the render group.

.. code-block::

   #replace userName with the actual user of your system
   sudo usermod -a -G render <userName>
