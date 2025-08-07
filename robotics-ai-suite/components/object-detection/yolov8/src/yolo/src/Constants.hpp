// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once
#include <string>
#include <vector>
#include <map>
#include <iostream>
#include <random>
#include <mutex>

#include <openvino/openvino.hpp>

#include <opencv2/core.hpp>

enum Task
{
    DETECTION,
    SEGMENTATION,
    POSE
};

static const map<string,Task> task_map = {
    {"detection",Task::DETECTION},
    {"segmentation",Task::SEGMENTATION},
    {"pose",Task::POSE}
};

string task_to_string( Task task )
{
    if ( task == DETECTION )
    {
        return "detection";
    }
    if ( task == SEGMENTATION )
    {
        return "segmentation";
    }
    if ( task == POSE )
    {
        return "pose";
    }
    return "unknown";
}

enum ModelSize
{
    N,
    S,
    M,
    L,
    XL
};

const unsigned long number_of_classes = 80;
const unsigned long number_of_masks = 32;
const unsigned long pose_points = 17;
const unsigned long values_per_point = 3;

const vector<string> classes{ "person",        "bicycle",      "car",
                              "motorcycle",    "airplane",     "bus",
                              "train",         "truck",        "boat",
                              "traffic light", "fire hydrant", "stop sign",
                              "parking meter", "bench",        "bird",
                              "cat",           "dog",          "horse",
                              "sheep",         "cow",          "elephant",
                              "bear",          "zebra",        "giraffe",
                              "backpack",      "umbrella",     "handbag",
                              "tie",           "suitcase",     "frisbee",
                              "skis",          "snowboard",    "sports ball",
                              "kite",          "baseball bat", "baseball glove",
                              "skateboard",    "surfboard",    "tennis racket",
                              "bottle",        "wine glass",   "cup",
                              "fork",          "knife",        "spoon",
                              "bowl",          "banana",       "apple",
                              "sandwich",      "orange",       "broccoli",
                              "carrot",        "hot dog",      "pizza",
                              "donut",         "cake",         "chair",
                              "couch",         "potted plant", "bed",
                              "dining table",  "toilet",       "tv",
                              "laptop",        "mouse",        "remote",
                              "keyboard",      "cell phone",   "microwave",
                              "oven",          "toaster",      "sink",
                              "refrigerator",  "book",         "clock",
                              "vase",          "scissors",     "teddy bear",
                              "hair drier",    "toothbrush" };


static const map<string,ModelSize> model_size_map = {
    {"n",ModelSize::N},
    {"s",ModelSize::S},
    {"m",ModelSize::M},
    {"l",ModelSize::L},
    {"x",ModelSize::XL}
};

static const map<size_t,ov::hint::PerformanceMode> performance_mode_map = {
    {1,ov::hint::PerformanceMode::LATENCY},
    {2,ov::hint::PerformanceMode::THROUGHPUT},
    {3,ov::hint::PerformanceMode::CUMULATIVE_THROUGHPUT}
};

static const map<size_t,ov::hint::Priority> priority_map = {
    {0,ov::hint::Priority::LOW},
    {1,ov::hint::Priority::MEDIUM},
    {2,ov::hint::Priority::HIGH}
};

static const map<size_t,ov::hint::ExecutionMode> precision_map = {
    {0,ov::hint::ExecutionMode::PERFORMANCE},
    {1,ov::hint::ExecutionMode::ACCURACY}
};

static const vector<string> task_strs_strings = { "", "-seg", "-pose" };
static const vector<string> task_names_strings = { "detection", "segmentation", "pose" };

static const vector<string> model_size_strings = { "n", "s", "m", "l", "x" };

int ov_element_to_cv_type( ov::element::Type type )
{
    if ( type == ov::element::f32 )
    {
        return CV_32FC1;
    }
    if ( type == ov::element::f16 )
    {
        return CV_16FC1;
    }
    std::cout << "\033[1;31m"
              << "Unsupported element type"
              << "\033[0m" << std::endl;
    throw;
}
