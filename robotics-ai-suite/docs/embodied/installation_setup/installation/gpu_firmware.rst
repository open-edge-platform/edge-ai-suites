Install Intel® GPU firmware (Optional)
======================================

The Embodied Intelligence SDK offers two options for installing Intel® GPU firmware: 

- **For platforms with only an integrated GPU (iGPU)**: automatic installation via the :doc:`Real-Time Linux <rt_linux>` method.
- **For platforms with both integrated (iGPU) and discrete GPUs (dGPU)**: manual installation using the instructions provided on this page.

Dependencies
:::::::::::::::::::::::::::

This firmware is part of a collection of kernel mode drivers
that together enable support for Intel graphics. The backports 
collection within https://github.com/intel-gpu includes:

  - `[i915] <https://github.com/intel-gpu/intel-gpu-i915-backports>`_ - The main graphics driver, |i915|.
  - `[cse] <https://github.com/intel-gpu/intel-gpu-cse-backports>`_ - |cse|.
  - `[pmt] <https://github.com/intel-gpu/intel-gpu-pmt-backports>`_ - |pmt|.
  - `[firmware] <https://github.com/intel-gpu/intel-gpu-firmware>`_ - Contains firmware required by |i915|.

Each project is tagged consistently so when pulling these repositories pull the same tag.

.. tip:: In |i915| is disabled, check the grub of cmdline:

    .. code-block:: console

        $ cat /proc/cmdline | grep i915
        i915.force_probe=*

Installation
:::::::::::::::::::::::::::

1. Get the correct |i915| firmware with the following command:

.. code-block:: bash

    $ wget https://web.git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git/plain/i915/mtl_gsc_1.bin --no-check-certificate
    $ wget https://web.git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git/plain/i915/mtl_guc_70.bin --no-check-certificate

2. Remove the ``zst`` firmware files with the following command (Optional):

.. code-block:: bash

    $ sudo rm /lib/firmware/i915/mtl_guc_70.bin.zst
    $ sudo rm /lib/firmware/i915/mtl_gsc_1.bin.zst

3. Update the |i915| firmware with the following command:

.. code-block:: bash

    $ sudo cp mtl_guc_70.bin /lib/firmware/i915/
    $ sudo cp mtl_gsc_1.bin /lib/firmware/i915/
    $ sudo update-initramfs -u -k $(uname -r)

4. Reboot.

Verifying Installation
:::::::::::::::::::::::::::

To verify that the GPU firmwares are installed, run ``sudo dmesg | grep firmware``, the result might be similar to the following:

.. code-block:: console

    [    2.619711] i915 0000:00:02.0: [drm] Finished loading DMC firmware i915/mtl_dmc.bin (v2.17)
    [    2.647487] i915 0000:00:02.0: [drm] GT0: GuC firmware i915/mtl_guc_70.bin version 70.36.0
    [    2.668723] i915 0000:00:02.0: [drm] GT1: GuC firmware i915/mtl_guc_70.bin version 70.36.0
    [    2.668725] i915 0000:00:02.0: [drm] GT1: HuC firmware i915/mtl_huc_gsc.bin version 8.5.4
    [    2.856236] i915 0000:00:02.0: [drm] GT1: Loaded GSC firmware i915/mtl_gsc_1.bin (cv1.0, r102.1.15.1926, svn 1)
