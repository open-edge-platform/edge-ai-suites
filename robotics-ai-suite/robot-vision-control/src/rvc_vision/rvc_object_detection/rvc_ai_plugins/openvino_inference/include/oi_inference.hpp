// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.

#pragma once

#include <opencv2/opencv.hpp>
#include <string>
#include <vector>

#include <openvino/openvino.hpp>
#include <queue>


namespace RVC_AI {
class OIInference : public RVCAIInterface
{
private:

    /** OpenVINO core*/
    ov::Core core;
    /** Preloaded model */
    std::shared_ptr<ov::Model> model;
    /** Compiled model, with pre and post processing*/
    ov::CompiledModel compiledModel;

    /** Queue of inference requests, for parallelization where possible*/
    std::queue<ov::InferRequest> idleRequests;

    /** Mutex protecting the inference queue*/
    std::mutex idleRequestsMutex;
    /** Condition for protecting the inference queue*/
    std::condition_variable idleRequestsCV;

    /** benchmarking variable*/
    std::chrono::high_resolution_clock::time_point startTime;
    /** benchmarking framerate */
    int frameRate;
    /** aspect ratio*/
    float m_ratio;
    /** rescaling padding width*/
    int m_pad_width;
    /** rescaling padding height*/    
    int m_pad_height;    
    /** resolution supporting variables*/
    int m_resX, m_resY;

    /** model input resx */
    int m_input_shape_x;
    /** model input resy */    
    int m_input_shape_y;

    /** yolo model version: v5 v6 or v8*/
    int model_version;
    /** Confidence threshold, below this value objects are ignored*/
    double confidence_threshold;
    /** Non maxima suppression threshold parameter */
    double nms_threshold;
    /** config parameter containing list of object name strings*/
    std::vector<std::string> class_name_array_param;

protected:

public:
    /**
     * @brief API entry point: define this plugin preprocessing operations
     *
     * @param inputImage cv::Mat input image to preprocess
     * @param outputImage preprocessed output cv::Mat
     * @return true on success
     * @return false otherwise
     */
    bool pre_process_image(const cv::Mat inputImage, cv::Mat & outputImage);
    /**
     * @brief API entry point: run the inference on input image
     *
     * @param image input image
     * @param output result output blob in cv::Mat format
     * @return true on success
     * @return false otherwise
     */
    bool run_inference_pipeline(const cv::Mat image, cv::Mat & output);
    /**
     * @brief API entry point: define the post processing to perform to retrieve the rotate bounding boxes
     *
     * @param input input blob cv::Mat
     * @param rotatedBBList output rotate Bounding box list
     * @return true on success
     * @return false otherwise
     */
    bool post_process_image(const cv::Mat input, rvc_vision_messages::msg::RotatedBBList & rotatedBBList);
    /**
     * @brief API entry: plugin initialization
     *
     * @param node Ros node
     * @param modelName input file name
     * @param bin secondary file name, optional
     * @param inference_device hardware device to run inferent on, std::string
     * @param model_version version of the model, if applicable
     * @return true on success
     * @return false otherwise
     */
    bool init(rclcpp::Node * node, const std::string & modelName);
    /** Constructor */
    OIInference();
};

} //RVC_AI Namespace
