.. _real_time_linux:

Real-Time Linux
#################

The Embodied Intelligence SDK provides real-time capabilities to the kernel with PREEMPT_RT patch and boot parameters for real-time optimization, which aims to increase predictability and reduce scheduler latencies.

Installation
================

1. Install GRUB customizations

.. code-block:: bash

    $ sudo apt install -y customizations-grub

2. Install linux-firmware

.. code-block:: bash

    $ sudo apt install -y linux-firmware

**Note:** |Linux| OS version 6.12 requires specific |i915| graphics microcontroller (guc), display microcontroller (dmc), and |gsc| (gsc) firmwares; these firmwares are installed in ``/lib/firmware/i915/experimental/``. Confirm the following boot parameters through ``cat /proc/cmdline`` after the next reboot:

.. code-block:: bash

    $ i915.guc_firmware_path=i915/experimental/mtl_guc_70.bin i915.dmc_firmware_path=i915/experimental/mtl_dmc.bin i915.gsc_firmware_path=i915/experimental/mtl_gsc_1.bin

If you cannot find the firmwares in ``/lib/firmware/i915/experimental/``, install the latest ``linux-firmware``:

.. code-block:: bash

   $ sudo apt install -y linux-firmware=20220329.git681281e4-0ubuntu3.36-intel-iotg.eci5

You can double check if the correct linux-firmware is in use:

.. code-block:: bash

   $ sudo apt-cache policy linux-firmware

Expected result:

.. code-block:: console

  linux-firmware:
    Installed: 20220329.git681281e4-0ubuntu3.36-intel-iotg.eci5

3. Install the real-time |Linux| kernel. For details, see :ref:`LinuxBSP <linuxbsp>`.

.. code-block:: bash

    $ sudo apt install -y linux-intel-rt-experimental

**Note:** If you don't need to use RT kernel, install with the following command:

.. code-block:: bash

    $ sudo apt install -y linux-intel-experimental

4. To modify default boot parameters, edit ``/etc/grub.d/10_eci_experimental``.

**Note:** Modify ``eci_cmdline_exp`` in ``/etc/grub.d/10_eci_experimental`` for a better real-time performance and power consumption:

.. code-block:: bash

    # Modify default cmdline parameters to enable cstate/pstate
    $ sudo sed -i 's/intel_pstate=disable intel.max_cstate=0 intel_idle.max_cstate=0 processor.max_cstate=0 processor_idle.max_cstate=0/intel_pstate=enable/g' /etc/grub.d/10_eci_experimental
    # Modify default cmdline parameter to affinity irq to core 0-9
    $ sudo sed -i 's/irqaffinity=0/irqaffinity=0-9/g' /etc/grub.d/10_eci_experimental
    # Modify default cmdline parameter to isolate cpus to core 10-13
    $ sudo sed -i 's/isolcpus=1,3 rcu_nocbs=1,3 nohz_full=1,3/isolcpus=10-13 rcu_nocbs=10-13 nohz_full=10-13/g' /etc/grub.d/10_eci_experimental
    $ sudo update-grub
    $ sudo reboot

4. Select `[Experimental] ECI Ubuntu` booting:

.. image:: assets/images/eci_grub.png
   :width: 65%
   :align: center

**Note:** Select ``Advanced Options for [Experimental] ECI Ubuntu`` to list ``[Experimental] ECI Ubuntu, with Linux 6.12.8-intel-ese-experimental-lts-rt`` for a real-time kernel or ``[Experimental] ECI Ubuntu, with Linux 6.12.8-intel-ese-experimental-lts`` for a generic kernel.

.. image:: assets/images/kernel_select.png
   :width: 65%
   :align: center

Real-time Runtime Optimization
================================

Per-core C-State Disable
:::::::::::::::::::::::::

Refer to :ref:`OS Setup <OS_Setup>` for BIOS optimization and |Linux| boot parameter optimization on real-time performance, Intel C-state and P-state are enabled. It brings more power consumption to improve on GPU AI performance, but C-state can introduce jitter due to the varying times required to transition between states in isolate cores. **Per-core C-state Disable** helps minimize this jitter, providing a more stable environment for real-time task.

Follow with below command to disable C-state in isolate core(e.g. core 13 as isolate core)

.. code-block:: bash

    # ! /bin/sh
    # Disable all cstates except C0 in isolate CPU cores
    # Define the range for CPU indices
    cpu_start=13  # Replace with your starting CPU index
    cpu_end=13   # Replace with your ending CPU index

    # Loop over each CPU index
    for (( i=cpu_start; i<=cpu_end; i++ )); do
        # Determine the maximum state index for the current CPU
        max_state_index=$(ls /sys/devices/system/cpu/cpu$i/cpuidle/ | grep -o 'state[0-9]*' | sed 's/state//' | sort -n | tail -1)

        # Loop over each state index
        for (( j=1; j<=max_state_index; j++ )); do
            # Disable the current state
            sudo echo 1 > /sys/devices/system/cpu/cpu$i/cpuidle/state$j/disable
            echo "Disabled CPU $i state $j"
        done
    done

Timer Migration Disable
:::::::::::::::::::::::::

In |Linux| kernel, timer migration refers to the process of moving timers from one CPU to another. This is often done to balance the load across CPUs or to optimize power management by consolidating timers on fewer CPUs when others are idle. Timer migration can lead to interference with other tasks running on the target CPU, potentially affecting real-time performance in isolate CPU core. By keeping timers on their original CPU, you minimize the risk of such interference.

Disabling timer migration in a real-time kernel helps maintain the consistency and predictability required for real-time applications, ensuring that timers are executed with minimal latency and interference.

Timer migration can be disabled with the following command:

.. code-block:: bash

    $ echo 0 > /proc/sys/kernel/timer_migration

Verify Benchmark Performance
===============================

After installing the real-time |Linux| kernel, it's a good idea to benchmark the system to establish confidence that the system is properly configured. Perform either of the following commands to install `Cyclictest <https://git.kernel.org/pub/scm/utils/rt-tests/rt-tests.git>`_. Cyclictest is most commonly used for benchmarking real-time systems. It is one of the most frequently used tools for evaluating the relative performance of an RT. Cyclictest accurately and repeatedly measures the difference between a thread’s intended wake-up time and the time at which it actually wakes up to provide statistics about the system’s latency. It can measure latency in real-time systems caused by the hardware, the firmware, and the operating system.
Please use ``rt-tests v2.6`` to collect performance, which support to pin threads to specific isolate core and avoid main thread in same core with the measurement threads.

Follow with below steps, you can find ``cyclictest v2.6`` in ``rt-tests-2.6``：

.. code-block:: bash

    $ wget https://web.git.kernel.org/pub/scm/utils/rt-tests/rt-tests.git/snapshot/rt-tests-2.6.tar.gz
    $ tar zxvf rt-tests-2.6.tar.gz
    $ cd rt-tests-2.6
    $ make

**Note**: Please ensure you had installed ``libnuma-dev`` as dependence before compilation.

  .. code-block:: bash

     $ sudo apt install libnuma-dev

An example command that runs the cyclictest benchmark as below:

.. code-block:: bash

    $ cyclictest -mp 99 -t1 -a 13 -i 1000 --laptop -D 72h  -N --mainaffinity 12

Default parameters are used unless otherwise specified. Run ``cyclictest --help`` to list the modifiable arguments.

.. list-table::
   :widths: 50 500
   :header-rows: 1

   * - option
     - Explanation
   * - -p
     - priority of highest priority thread
   * - -t
     - one thread per available processor
   * - -a
     - Run thread #N on processor #N, or if CPUSET given, pin threads to that set of processors in round-robin order
   * - -i
     - base interval of thread in us default=1000
   * - -D
     - specify a length for the test run
   * - -N
     - print results in ns instead of us(default us)
   * - --mainaffinity
     - Run the main thread on CPU #N. This only affects the main thread and not the measurement threads
   * - -m
     - lock current and future memory allocations
   * - --laptop
     - Not setting ``cpu_dma_latency`` to save battery, recommend using it when enabling per-core C-state disable.  

On a **realtime-enabled** system, the result might be similar to the following:

.. code-block:: console

    T: 0 ( 3407) P:99 I:1000 C: 100000 Min:      928 Act:   1376 Avg:   1154 Max:      18373

This result indicates an apparent short-term worst-case latency of 18 us. According to this, it is important to pay attention to the Max values as these are indicators of outliers. Even if the system has decent Avg (average) values, a single outlier as indicated by Max is enough to break or disturb a real-time system.

If the real-time data is not good by default installation, please refer to :ref:`OS Setup <OS_Setup>` for BIOS optimization and `Optimize Performance <https://eci.intel.com/docs/3.3/development/performance.html>`_ to optimize |Linux| OS and application runtime on |Intel| Processors.
