|oneAPI|
##########

`Intel® oneAPI <https://www.intel.com/content/www/us/en/developer/tools/oneapi/overview.html>`_ is a cross-industry, open, standards-based unified programming model that provides a common developer experience across accelerator architectures, which provides a comprehensive set of libraries, open source repositories, SYCL-based C++ language extensions, and optimized reference implementations.

.. image:: assets/images/oneapi.png
         :width: 100%
         :align: center

Robotics software developers can use the |oneAPI| toolkit and |oneAPI|-powered applications to enhance AI deep learning and heterogeneous computing capabilities, thereby leveraging the full value of all hardware.

Intel® oneAPI Base Toolkit
===========================
The Intel® oneAPI Base Toolkit (Base Kit) is a core set of tools and libraries for developing high-performance, data-centric applications across diverse architectures. It features an industry-leading C++ compiler that implements SYCL*, an evolution of C++ for heterogeneous computing.

It includes:

.. list-table::
   :widths: 30 50
   :align: center
   :header-rows: 0

   * - Intel® oneAPI DPC++/C++ Compiler
     - Compile and optimize C++ and SYCL code for CPU, GPU, and FPGA target architectures.
   * - Intel® oneAPI DPC++ Compatibility Tool
     - Migrate legacy CUDA code to open multiarchitecture SYCL code with this assistant.
   * - Intel® VTune™ Profiler
     - Find and optimize performance bottlenecks across CPU, GPU, and FPGA systems.
   * - Intel® Advisor
     - Design code for efficient vectorization, threading, and offloading to accelerators.
   * - Intel® Distribution for GDB*
     - Enable deep, system-wide debug of SYCL, C, C++, and Fortran code.
   * - Intel® oneAPI DPC++ Library
     - Speed up data parallel workloads with these key productivity algorithms and functions.
   * - Intel® oneAPI Threading Building Blocks
     - Simplify parallelism with this advanced threading and memory-management template library.
   * - Intel® oneAPI Math Kernel Library
     - Accelerate math processing routines, including matrix algebra, fast Fourier transforms (FFT), and vector math.
   * - Intel® Integrated Performance Primitives
     - Speed up performance of imaging, signal processing, data compression, cryptography, and more.
   * - Intel® Cryptography Primitives Library
     - Secure, fast, lightweight building blocks for cryptography optimized for Intel CPUs.
   * - Intel® oneAPI Data Analytics Library
     - Boost machine learning and data analytics performance.
   * - Intel® oneAPI Deep Neural Network Library
     - Develop fast neural networks on Intel CPUs and GPUs with performance-optimized building blocks.
   * - Intel® oneAPI Collective Communications Library
     - Implement optimized communication patterns to distribute deep learning model training across multiple nodes.
   * - FPGA Support Package for the Intel® oneAPI DCP++/C++ Compiler (separate download required)
     - Accelerate your register transfer level (RTL) development with SYCL high-level synthesis (HLS), or program FPGA accelerators to speed up specialized, data-centric workloads. Requires installation of the Base Kit.

| `Intel® oneAPI Base Toolkit Overview <https://www.intel.com/content/www/us/en/develop/tools/oneapi/base-toolkit.html>`_ page for more information.

.. _oneapi_install_label:

To Install the |oneAPI| **2024.2.1** with the following steps:

1. From the `oneAPI website <https://www.intel.com/content/www/us/en/developer/tools/oneapi/base-toolkit-download.html?packages=oneapi-toolkit&oneapi-toolkit-os=linux&oneapi-lin=offline>`_, locate the downloaded install file.

2. To launch the GUI installer as the root, do one of the following:

.. code-block:: bash

  # launch the GUI installer as the root
  $ sudo sh ./l_BaseKit_p_2024.2.1.100_offline.sh
  
  # Optionally, to launch the GUI installer as the current user
  $ sh ./l_BaseKit_p_2024.2.1.100_offline.sh

3. Follow the instructions in the installer.

Intel® oneAPI HPC Toolkit
===========================

High-performance computing (HPC) is at the core of AI, machine learning, and deep learning applications. Intel® oneAPI HPC Toolkit delivers what developers need to build, analyze, optimize, and scale HPC applications with the latest techniques in vectorization, multi-threading, multi-node parallelization, and memory optimization. 

It includes:

.. list-table::
   :widths: 30 50
   :align: center
   :header-rows: 0

   * - Intel® Fortran Compiler
     - Compile and optimize standard Fortran code for CPU and GPU architectures.
   * - Intel® MPI Library
     - Deliver flexible, efficient, scalable cluster messaging on CPU and GPU architectures and a variety of network fabrics.
   * - Intel® oneAPI DPC++/C++ Compiler
     - Compile and optimize C++ and SYCL code for CPU, GPU, and FPGA target architectures.
   * - Intel® oneAPI DPC++ Compatibility Tool
     - Migrate legacy CUDA code to open multiarchitecture SYCL code with this assistant.
   * - Intel® VTune™ Profiler
     - Find and optimize performance bottlenecks across CPU, GPU, and FPGA systems.
   * - Intel® Advisor
     - Design code for efficient vectorization, threading, and offloading to accelerators.
   * - Intel® Distribution for GDB*
     - Enable deep, system-wide debug of SYCL, C, C++, and Fortran code.
   * - Intel® oneAPI DPC++ Library (oneDPL)
     - Speed up data parallel workloads with these key productivity algorithms and functions.
   * - Intel® oneAPI Threading Building Blocks (oneTBB)
     - Simplify parallelism with this advanced threading and memory-management template library.
   * - Intel® oneAPI Math Kernel Library (oneMKL)
     - Accelerate math processing routines, including matrix algebra, fast Fourier transforms (FFT), and vector math.
   * - Intel® Integrated Performance Primitives 
     - Speed up performance of imaging, signal processing, data compression, cryptography, and more.
   * - Intel® Cryptography Primitives Library  
     - Secure, fast, lightweight building blocks for cryptography optimized for Intel CPUs.
   * - Intel® oneAPI Data Analytics Library (oneDAL)
     - Boost machine learning and data analytics performance.
   * - Intel® oneAPI Deep Neural Network Library (oneDNN)
     - Develop fast neural networks on Intel CPUs and GPUs with performance-optimized building blocks.
   * - Intel® oneAPI Collective Communications Library (oneCCL)
     - Implement optimized communication patterns to distribute deep learning model training across multiple nodes.
   * - FPGA Support Package for the Intel® oneAPI DCP++/C++ Compiler (separate download required)
     - Accelerate your register transfer level (RTL) development with SYCL high-level synthesis (HLS), or program FPGA accelerators to speed up specialized, data-centric workloads. Requires installation of the Base Kit.

| `Intel® oneAPI HPC Toolkit Overview <https://www.intel.com/content/www/us/en/develop/tools/oneapi/hpc-toolkit.html>`_ page for more information.
