# Use the GPU ORB Extractor

This tutorial shows how to use the GPU orb-extractor feature library API.

The GPU orb-extractor feature library offers thread-safe support for both single and multiple cameras.

This tutorial illustrates GPU orb-extractor feature library usage with OpenCV `cv::Mat` and `cv::Keypoints`. It explains using multiple CPU threads with multiple ORB extractor objects, as well as using a single orb-extractor feature object to handle multiple camera inputs.

The multithread feature provides more flexibility for Visual SLAM to call multiple objects of the orb-extractor feature library.

## Prerequisites

Complete the [Robot on Intel Getting Started Guide](../../../../gsg_robot/index.md) before continuing.

## Tutorial

> **Note:** This tutorial can be run both inside and outside a Docker image. It assumes that the `liborb-lze-dev` Deb package is installed and the user has copied the tutorial directory from `/opt/intel/orb_lze/samples/` to a user-writable directory.

1. Prepare the environment:

```bash
sudo apt install liborb-lze-dev libgflags-dev
cp -r /opt/intel/orb_lze/samples/ ~/orb_lze_samples
cd ~/orb_lze_samples/
```

2. `main.cpp` should be in the directory ([view it on GitHub](https://github.com/open-edge-platform/edge-ai-suites/blob/main/robotics-ai-suite/docs/robotics/sources/sample/main.cpp)).

3. Build the code:

```bash
mkdir build && cd build
cmake ../
make -j
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

> **Note:** You can specify the number of images per thread and the number of threads to execute. You can process multiple image inputs within a single thread of the extract API, or process one or more image inputs using multiple threads with extract API calls.

## Code Explanation

- Configuration for the ORB extractor.

```cpp
constexpr uint32_t max_num_keypts_ = 2000;
constexpr int num_levels_ = 8;
constexpr int ini_fast_thr_ = 20;
constexpr int min_fast_thr_ = 7;
constexpr float scale_factor_ = 1.2f;
```

- Initialize the input and output parameters:

```cpp
    int num_of_cameras = num_cam;
    std::vector<cv::Mat> all_images;
    all_images.resize(num_of_cameras);
    for(int i = 0; i < num_of_cameras; i++)
    {
       all_images[i] = cv::imread(image_path, cv::IMREAD_GRAYSCALE);
    }

    std::vector<std::vector<KeyType>> keypts(num_of_cameras);
    std::vector<MatType> all_descriptors(num_of_cameras);

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
    const cv::_InputArray in_image_array(all_images);
    const cv::_InputArray in_image_mask_array;
    const cv::_OutputArray descriptor_array(all_descriptors);
#endif
```

- Create `orb_extractor` object:

```cpp
auto extractor = std::make_shared<orb_extractor>(max_num_keypts_, scale_factor_, num_levels_, ini_fast_thr_, min_fast_thr_, num_of_cameras, mask_rect);
```

- Set GPU kernel path (specify the path to GPU binaries such as `gaussian_genx.bin`, `resize_genx.bin`):

```cpp
extractor->set_gpu_kernel_path(ORBLZE_KERNEL_PATH_STRING);
```

> **Note:** The macro `ORBLZE_KERNEL_PATH_STRING` is defined as `"/usr/lib/x86_64-linux-gnu"` in `config.h`.
> This header file is installed by the Deb package `liborb-lze-dev` at `/usr/include/config.h`.

- Call the extract function to output the keypoints and descriptors for all camera input images.
Depending on the number of camera inputs, the orb-extractor feature library returns the vectors of keypoints number and descriptors:

```cpp
extractor->extract(in_image_array, in_image_mask_array, keypts, descriptor_array);
```

- Draw keypoints on the image and store them in the corresponding `cv::Mat` vector:

```cpp
std::vector<cv::Mat> out;
out.resize(num_of_cameras);

thread_id  =  thread_id + "_and_";

for( int i = 0; i < num_of_cameras; i++)
{
    out.at(i).create(all_images.at(i).rows, all_images.at(i).cols, CV_8U);
    cv::drawKeypoints(all_images.at(i), all_keypts[i], out[i], cv::Scalar(255,0,0));
    char no[20];
    sprintf(no,"Img:%d",i+1);
    All_Images obj;
    obj.image_title = thread_id + no;
    obj.img = out[i];
    gl_images.push_back(obj);
}
```

- Create multiple threads. Each thread creates one orb-extractor feature object:

```cpp
std::vector<std::thread> threads;

 for (int i = 0; i < num_of_threads; ++i)
 {
     std::string thread_name = "Thread:" + std::to_string(i + 1);
     threads.emplace_back(extract, num_images, image_path.c_str(), thread_name, num_of_iter);
 }
 for (auto& thread : threads)
     thread.join();
```

- Display images:

```cpp
for (int i = 0; i < (num_images * num_of_threads); i++)
{
    cv::imshow(gl_images[i].image_title, gl_images[i].img);
}
cv::waitKey(0);
```
