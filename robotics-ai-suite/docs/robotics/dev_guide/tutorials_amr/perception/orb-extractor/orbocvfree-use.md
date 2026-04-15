# Use GPU ORB Extractor with OpenCV-free Library

This tutorial demonstrates how to use the GPU orb-extractor feature OpenCV-free library.
The GPU orb-extractor feature OpenCV-free library provides similar features, except input and output structures are defined within this library.

## Tutorial

1. Prepare the environment:

   ```bash
   cd /opt/intel/orb_lze/samples/
   ```

2. `main.cpp` should be in the directory. [View it on GitHub](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/docs/robotics/sources/sample/main.cpp) to read the comments for the code.

   > **Note:** Refer to the explanations in the [Use the GPU ORB Extractor](./api-use.md) tutorial for details on how to use the orb-extractor feature library API.

3. Build the code:

   ```bash
   cp -r /opt/intel/orb_lze/samples/ ~/orb_lze_samples
   cd ~/orb_lze_samples/
   mkdir build
   cd build
   cmake -DBUILD_OPENCV_FREE=ON ../
   make -j$(nproc)
   ```

4. Run the binary:

   ```bash
   ./feature_extract -h
   ```

   - Available command line arguments:

   ```text
   Usage: ./feature_extract --images=<> --image_path=<> --threads=<>

     --images <integer>     : Number of images or number of cameras. Default value: 1
     --image_path <string>  : Path to input image files. Default value: image.jpg
     --threads <integer>    : Number of threads to run. Default value: 1
     --iterations <integer> : Number of iterations to run. Default value: 10
   ```

   - The following command runs four threads, each thread taking two camera image inputs:

   ```bash
   ./feature_extract --images=2 --threads=4
   ```

5. Expected results example:

   ```text
   ./feature_extract --images=2 --threads=4
    iteration 10/10
    Thread:2: gpu host time=21.4233
    iteration 10/10
    Thread:1: gpu host time=21.133
    iteration 10/10
    Thread:4: gpu host time=20.9086
    iteration 10/10
    Thread:3: gpu host time=20.6155
   ```

   After execution, the input image displays keypoints as blue dots.

   ![ORB extraction output](../../../../images/orb_extract_out.jpg "orb extraction output")

   > **Note:** You can specify the number of images per thread and the number of threads to execute.
   > You can process multiple image inputs within a single thread of the extract API, or process one or more image inputs using multiple threads with extract API calls.
