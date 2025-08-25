 .. _orb-extractor-api:

Tutorial to Use GPU ORB Extractor Feature
=============================================

This tutorial shows how to use GPU orb-extractor feature library API.

The GPU orb-extractor feature library offers thread-safe support for both single and multiple cameras.

This tutorial illustrates GPU orb-extractor feature library usage with OpenCV ``cv::Mat and cv::Keypoints``.
It explains employing multiple CPU threads with multiple ORB extractor objects, as well as using a single orb-extractor feature object to handle multiple camera inputs.

The multithread feature provides more flexibility for visual SLAM to call multiple objects of the orb-extractor feature library.

.. note::

   This tutorial can be run both inside and outside a Docker* image. We assume that the ``liborb-lze-dev`` |deb_pack| has been installed,
   and the user has copied the tutorial directory from ``/opt/intel/orb_lze/samples/`` to a user-writable directory.

#. Prepare the environment:

   .. code-block::

      sudo apt install liborb-lze-dev
      cp -r /opt/intel/orb_lze/samples/ ~/orb_lze_samples
      cd ~/orb_lze_samples/

#. ``main.cpp`` should be in the directory with following content:

   .. literalinclude:: ../../../../sources/sample/main.cpp
      :language: cpp
      :linenos:

#. Build the code:

   .. code-block::

      mkdir build && cd build
      cmake ../
      make -j

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
.....................................................................................

Configuration for the ORB extractor:

.. literalinclude:: ../../../../sources/sample/main.cpp
   :language: cpp
   :lines: 13-17

Initialize the input and output parameters:

.. literalinclude:: ../../../../sources/sample/main.cpp
   :language: cpp
   :lines: 37-61

Create orb_extract object:

.. literalinclude:: ../../../../sources/sample/main.cpp
   :language: cpp
   :lines: 69

*Set gpu kernel path:* Specify the path to GPU binaries such as gaussian_genx.bin, resize_genx.bin.

.. literalinclude:: ../../../../sources/sample/main.cpp
   :language: cpp
   :lines: 70

.. note::

   The macro ORBLZE_KERNEL_PATH_STRING is defined as *"/usr/lib/x86_64-linux-gnu"* in the header file ``config.h``.
   This header file is installed by the |deb_pack| ``liborb-lze-dev`` at */usr/include/config.h*.

Call the extract function to output the keypoints and descriptors for all camera input images.
Depending on the number of camera inputs, the orb-extractor feature library returns the number of the keypoints vector and the descriptors vector.

.. literalinclude:: ../../../../sources/sample/main.cpp
   :language: cpp
   :lines: 79

Draw the keypoints on the image. Keypoints are drawn on the image and stored in respective CV:Mat vector.

.. literalinclude:: ../../../../sources/sample/main.cpp
   :language: cpp
   :lines: 112-127

Create multiple threads. Each thread will create one orb-extractor feature object.

.. literalinclude:: ../../../../sources/sample/main.cpp
   :language: cpp
   :lines: 142-150

Display images:

.. literalinclude:: ../../../../sources/sample/main.cpp
   :language: cpp
   :lines: 152-157
