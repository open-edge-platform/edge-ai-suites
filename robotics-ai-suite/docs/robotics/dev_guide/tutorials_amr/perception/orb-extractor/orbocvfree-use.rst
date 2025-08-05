.. _orb-orbocvfree-use:

Using GPU ORB Extractor Feature with OpenCV-free Library.
======================================================================

This tutorial demonstrates how to use the GPU orb-extractor feature OpenCV-free library.
The GPU orb-extractor feature OpenCV free library provides similar features except input and output structures are defined within this library.

#. Prepare the environment

   .. code-block::

      cd /opt/intel/orb_lze/samples/

#. ``main.cpp`` should be in the directory with following content:

   .. note::
      Refer to the main.cpp file as explained in the tutorial, for utilizing GPU orb-extractor feature :ref:`orb-extractor-api`.

#. Build the code:

   .. code-block::

      cp -r /opt/intel/orb_lze/samples/ ~/orb_lze_samples
      cd ~/orb_lze_samples/
      mkdir build
      cd build
      cmake -DBUILD_OPENCV_FREE=ON ../
      make -j$(nproc)

#. Run the binary:

   .. code-block::

      ./feature_extract -h

      Following are the command line arguments:

      Usage: ./feature_extract --images=<> --image_path=<> --threads=<>

        --images <integer>     :  Number of images or number of cameras. Default value: 1
        --image_path <string>  :  Path to input image files. Default value: image.jpg
        --threads <integer>    :  Number of threads to run. Default value: 1
        --iterations <integer> :  Number of iterations to run. Default value: 10

      The following command, it will run four threads, each thread is taking two cameras image input.

      ./feature_extract --images=2 --threads=4

   After executing, the input image will display keypoints in blue color dots.

#. Expected results example:

   .. code-block::

      ./feature_extract --images=2 --threads=4
       iteration 10/10
       Thread:2: gpu host time=21.4233
       iteration 10/10
       Thread:1: gpu host time=21.133
       iteration 10/10
       Thread:4: gpu host time=20.9086
       iteration 10/10
       Thread:3: gpu host time=20.6155

After executing, the input image will display keypoints in blue color dots.

   .. image:: ../../../../images//orb_extract_out.jpg


.. note::

      Here, you can specify the number of images per thread and the number of threads to be executed.
      You have the option to process multiple image inputs within a single thread of the extract API or to process a single
      or more images input using multiple threads with extract API calls.

Code Explanation
--------------------

Initialize the input and output parameters:

.. literalinclude:: ../../../../sources/sample/main.cpp
   :language: cpp
   :lines: 47-57

The above code illustrates how to store images in Mat2d class object.

.. note::

    Based on BUILD_OPENCV_FREE=ON, only OpenCV-free dependency code will compile and link to the ``libgpu_orb_ocvfree.so`` library.
    Orb-extractor feature libraries have their own defined classes for *image input* and *keypoint output*.
    For more details, see the */usr/include/orb_type.h* file.
    This file is installed by the |deb_pack| ``liborb-lze-dev``.

The vector of keypts can be used by application, or convert to different type. This example show how to convert ORB extractor ``KeyPoint`` to ``cv::KeyPoint``.

.. literalinclude:: ../../../../sources/sample/main.cpp
   :language: cpp
   :lines: 94-105
