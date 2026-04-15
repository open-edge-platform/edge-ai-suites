# GPU ORB Extractor Feature Overview

The orb-extractor feature takes an input image and provides keypoints (spatial locations or points in the image that define what is interesting) and descriptor data for those keypoints of that input image.

The library implements the orb-extractor feature, running on a GPU.

This orb-extractor feature can be easily integrated into Visual SLAM. After initializing the orb-extractor feature object, the extract function can be called for every input frame. The extract function returns a set of keypoints and descriptors.

The orb-extractor feature is constructed from various GPU kernels, including image resize, Gaussian operations, FAST feature extraction, and descriptor and orientation calculations. It interfaces with the GPU via the oneAPI Level Zero interface, with the GPU kernels developed using the C-for-Metal SDK.

The orb-extractor feature library enables users to generate multiple orb-extractor objects tailored to their applications. Additionally, a single orb-extractor feature object can process input from one or multiple camera sources, providing versatile support for various configurations in Visual SLAM front-ends.

The orb-extractor feature library provides two binary files: one linked with the OpenCV library and another without it. The OpenCV-linked version handles input and output using OpenCV objects like `cv::Mat` and `cv::KeyPoints`. The version not dependent on OpenCV uses the internally defined input and output formats within the orb-extractor feature library.

## System Requirements

- Ubuntu 22.04 LTS.
- OpenCV 4.5.4.

## Hardware Requirements

Any of the following CPU platforms with integrated Intel GPU:

- 13th Generation Intel® Core™ i3/i5/i7 Processors
- 12th Generation Intel® Core™ i3/i5/i7 Processors
- 11th Generation Intel® Core™ i3/i5/i7 Processors
- 10th Generation Intel® Core™ i3/i5/i7 Processors
- 6th to 9th Generation Intel® Core™ i3/i5/i7 Processors

## Deb Packages

- `liborb-lze` - Includes host libraries `libgpu_orb.so`, `libgpu_orb_ocvfree.so`, and compiled GPU kernels.
- `liborb-lze-dev` - Sample code to show how to use the library.

## Prerequisites

Complete the [Robot on Intel Getting Started Guide](../../../../gsg_robot/index.md) before continuing.

## Install Deb Packages

```bash
sudo apt install liborb-lze-dev liborb-lze
```

Upon installing the orb-extractor feature Deb packages, a dialog box displaying architecture images appears. Choose the appropriate architecture from this selection.

![ORB architecture selection](../../../../images/orb_slect_arch.jpg)

Select the right architecture according to this table:

| Processor | Architecture |
| --- | --- |
| 13th Generation Intel® Core™ i3/i5/i7 Processors | gen 12lp |
| 12th Generation Intel® Core™ i3/i5/i7 Processors | gen 12lp |
| 11th Generation Intel® Core™ i3/i5/i7 Processors | gen 12lp |
| 10th Generation Intel® Core™ i3/i5/i7 Processors | gen 11 |
| 6th to 9th Generation Intel® Core™ i3/i5/i7 Processors | gen 9 |
