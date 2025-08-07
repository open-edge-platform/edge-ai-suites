// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once
#include <string>
#include <vector>
#include <sstream>
#include "opencv2/core.hpp"

#include "Detection.hpp"


struct Detection
{
    int class_id{ 0 };
    string className{};
    float confidence{ 0.0 };
    cv::Scalar color{};
    cv::Rect box{};
    vector<float> mask{};
    vector<float> pose{};

    string toString()
    {
        stringstream ss;
        ss << "Class: " << className << endl;
        ss << "Confidence: " << confidence << endl;
        ss << "Box: " << box << endl;
        return ss.str();
    }

};
