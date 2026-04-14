# Use GPU ORB Extractor with OpenCV-free Library

This tutorial demonstrates how to use the GPU orb-extractor feature OpenCV-free library.
The GPU orb-extractor feature OpenCV-free library provides similar features, except input and output structures are defined within this library.

1. Prepare the environment:

```bash
cd /opt/intel/orb_lze/samples/
```

2. `main.cpp` should be in the directory ([view it on GitHub](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/docs/robotics/sources/sample/main.cpp)).

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

## Code Explanation

- Initialize the input and output parameters:

```cpp
#ifdef OPENCV_FREE
    Mat2d *images = new Mat2d[num_of_cameras];
    std::vector<MatType> in_image_array;
    for( int i = 0; i < num_of_cameras; i++)
    {
        images[i] = Mat2d(all_images[i].rows, all_images[i].cols, all_images[i].data);
        in_image_array.push_back(images[i]);
    }
    std::vector<MatType> in_image_mask_array;
    std::vector<MatType> descriptor_array;
#else
```

The code above shows how to store images in a `Mat2d` class object.

> **Note:** Based on `BUILD_OPENCV_FREE=ON`, only OpenCV-free dependency code compiles and links to the `libgpu_orb_ocvfree.so` library.
> Orb-extractor feature libraries define their own classes for image input and keypoint output.
> For details, see the `/usr/include/orb_type.h` file, installed by the Deb package `liborb-lze-dev`.

- The vector of keypoints can be used directly by the application or converted to a different type. This example shows how to convert ORB extractor `KeyPoint` to `cv::KeyPoint`:

```cpp
#ifdef OPENCV_FREE
    for(int i=0; i < num_of_cameras; i++)
    {
        auto& gpu_keypts = keypts.at(i);
        for (int pt=0; pt < gpu_keypts.size(); pt++)
        {
            all_keypts[i].emplace_back(cv::KeyPoint(gpu_keypts[pt].x, gpu_keypts[pt].y,
                        gpu_keypts[pt].size, gpu_keypts[pt].angle, gpu_keypts[pt].response,
                        gpu_keypts[pt].octave, -1));
        }
    }
#else
```
