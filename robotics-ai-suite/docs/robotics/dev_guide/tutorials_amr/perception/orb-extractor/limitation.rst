.. _orb-limitation:

GPU ORB Extractor Feature Limitation
######################################

#. To use the multiple camera images feature on a single orb-extractor feature object, all input images must have the same width and height.  
#. For different-sized images, create a separate orb-extractor feature object for each image. Spawn a new thread for concurrency execution.

Troubleshooting
--------------------------------------------------------------------------------

If a segmentation fault occurs, please follow these steps:

.. code-block::

   #Do confirm gpu driver is loaded or not
   lsmod | grep i915

   #Add the current user to the render group
   sudo usermod -a -G render <userName>

