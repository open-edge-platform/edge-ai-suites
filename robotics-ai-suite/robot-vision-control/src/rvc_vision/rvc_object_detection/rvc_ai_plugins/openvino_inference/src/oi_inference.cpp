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

#include "ament_index_cpp/get_package_share_directory.hpp"
#include "rvc_ai_interface.hpp"
#include "oi_inference.hpp"

#include <rclcpp/rclcpp.hpp>

namespace RVC_AI {

OIInference::OIInference() :
    confidence_threshold(0.7),
    nms_threshold(0.5)
{
    /** default values for 640x480 when model input is square. will be overwritten*/
    m_ratio = 1;
    m_pad_height = 80;
    m_pad_width = 0;
    frameRate = 30;
    m_resX = 640;
    m_resY = 480;
    m_input_shape_x = m_input_shape_y = 640;
    model_version = 5;
}

//TODO: check for failures
bool OIInference::init(rclcpp::Node * node, const std::string & modelName)
{
    (void)node;

    node->declare_parameter<std::string>("model_format", "openvino");
    node->declare_parameter<int>("model_version", 5);
    node->declare_parameter<std::string>("inference_device", "GPU");
    node->declare_parameter<double>("confidence_threshold", 0.7);
    node->declare_parameter<double>("nms_threshold", 0.5);
    node->declare_parameter<std::string> ( "rvc_use_case_binaries", "rvc_use_case_binaries" );
    node->declare_parameter<int>("resX", 640);
    node->declare_parameter<int>("resY", 480);
    node->declare_parameter<std::vector<std::string>>("class_name_array",
        std::vector<std::string>({"bolt", "gear", "nut", "cube"}) );    
    
    
    class_name_array_param = node->get_parameter("class_name_array").as_string_array();

    auto model_format_param = node->get_parameter("model_format").as_string();
    auto model_version_param = node->get_parameter("model_version").as_int();
    auto inference_device = node->get_parameter("inference_device").as_string();

    auto model_path = ament_index_cpp::get_package_share_directory( node->get_parameter(
            "rvc_use_case_binaries").as_string()) + "/ai_models/";
    confidence_threshold = node->get_parameter("confidence_threshold").as_double();
    nms_threshold = node->get_parameter("nms_threshold").as_double();

    auto resx_param = node->get_parameter("resX").as_int();
    auto resy_param = node->get_parameter("resY").as_int();

    std::string xml_file, bin_file;

    if (model_format_param == "onnx")
    {
        xml_file = model_path + modelName + ".onnx";
        bin_file = "";
        RCLCPP_INFO(node->get_logger(), "Looking for ONNX Model File %s", xml_file.c_str());
    }
    else
    {
        xml_file = model_path + modelName + ".xml";
        bin_file = model_path + modelName + ".bin";
        RCLCPP_INFO(node->get_logger(), "Looking for OpenVino Model Files %s", xml_file.c_str());
    }


    model_version = model_version_param;

    RCLCPP_INFO(node->get_logger(), " OpenVINO plugin: Model Version: %d", model_version);

    ov::AnyMap config{{ov::hint::performance_mode.name(), ov::hint::PerformanceMode::THROUGHPUT}};

    RCLCPP_INFO(node->get_logger(), "OpenVINO plugin: loading Model %s", xml_file.c_str());

    model = core.read_model(xml_file);

    const std::vector<ov::Output<ov::Node>> inputs = model->inputs();

    for (const ov::Output<const ov::Node> input : inputs)
    {
        RCLCPP_INFO_STREAM(rclcpp::get_logger("OI"), "    inputs");

        const std::string name = input.get_names().empty() ? "NONE" : input.get_any_name();
        RCLCPP_INFO_STREAM(rclcpp::get_logger("OI"), "        input name: " << name);

        const ov::element::Type type = input.get_element_type();
        RCLCPP_INFO_STREAM(rclcpp::get_logger("OI"), "        input type: " << type);

        const ov::Shape shape = input.get_shape();
        RCLCPP_INFO_STREAM(rclcpp::get_logger("OI"), "        input shape: " << shape);
        m_input_shape_x = shape[2];
        m_input_shape_y = shape[3];

    }

    ov::preprocess::PrePostProcessor ppp(model);
    ov::preprocess::InputInfo & input_info = ppp.input();

    auto squared_size = resx_param > resy_param ? resx_param : resy_param;
    input_info.tensor()
        .set_element_type(ov::element::u8)
        .set_layout("NHWC")
        .set_spatial_static_shape(squared_size, squared_size);


    input_info.model().set_layout("NCHW");

    input_info.preprocess()
        .convert_element_type(ov::element::f32)
        .resize(ov::preprocess::ResizeAlgorithm::RESIZE_LINEAR, m_input_shape_x, m_input_shape_x)
        .mean(0.5f)
        .scale(255.0f);
    model = ppp.build();

    RCLCPP_INFO_STREAM(rclcpp::get_logger("OI"), " PREPROC: " << ppp);

    compiledModel = core.compile_model(model, inference_device, config);

    uint32_t nireq = compiledModel.get_property(ov::optimal_number_of_infer_requests);

    RCLCPP_INFO(rclcpp::get_logger("OI"), "optimal_number_of_infer_requests: %d", nireq);

    for (uint32_t i = 0; i < nireq; ++i)
    {
        idleRequests.push(compiledModel.create_infer_request());
    }

    startTime = std::chrono::high_resolution_clock::now();
    return true;
}

bool OIInference::pre_process_image(const cv::Mat inputImage, cv::Mat & outputImage)
{

    cv::Mat nn_input_blob, nn_output;
    cv::Mat output;

    static cv::Size nn_input_size(m_input_shape_x, m_input_shape_y);
    static cv::Scalar border_color(114, 114, 114);

    m_resX = inputImage.cols;
    m_resY = inputImage.rows;


    if (m_resX > m_resY)
    {
        m_pad_height = (m_resX - m_resY) / 2;
        m_pad_width = 0;
        m_ratio = nn_input_size.width / (double)m_resX;
    }
    else
    {
        m_pad_width = (m_resY - m_resX) / 2;
        m_pad_height = 0;
        m_ratio = nn_input_size.height / (double)m_resY;
    }

    cv::copyMakeBorder(
        inputImage, outputImage, m_pad_height, m_pad_height, m_pad_width, m_pad_width,
        cv::BORDER_CONSTANT, border_color);
    return true;

}

bool OIInference::run_inference_pipeline(const cv::Mat input, cv::Mat & outputImage)
{
    try
    {
        ov::InferRequest infer_request;

        std::unique_lock<std::mutex> lock(idleRequestsMutex);

        while (idleRequests.empty())
        {
            idleRequestsCV.wait(lock);
        }

        if (!idleRequests.empty())
        {
            infer_request = idleRequests.front();
            idleRequests.pop();
            lock.unlock();
            ov::Tensor output_tensor;
            infer_request.set_callback(
                [&infer_request, &output_tensor, this](std::exception_ptr ex)
                {
                    (void)ex;
                    std::unique_lock<std::mutex> lock(idleRequestsMutex);
                    idleRequests.push(infer_request);
                    output_tensor = infer_request.get_output_tensor();
                    idleRequestsCV.notify_one();
                });

            auto input_tensor = ov::Tensor(
                infer_request.get_input_tensor().get_element_type(),
                infer_request.get_input_tensor().get_shape(), input.data);

            infer_request.set_input_tensor(input_tensor);

            infer_request.start_async();
            infer_request.wait();

            auto shape = output_tensor.get_shape();

            cv::Mat nn_output_squeezed = cv::Mat(
                shape[1], shape[0] * shape[2], CV_32FC1,
                (void *)output_tensor.data<ov::fundamental_type_for<ov::element::Type_t::f32>>());

            if (model_version == 8)
            {
                RCLCPP_INFO(rclcpp::get_logger("OI"), " Yolo V8: transposing...");
                nn_output_squeezed = nn_output_squeezed.t();
            }

            outputImage = std::move(nn_output_squeezed);
            return true;
        }
    } catch (std::exception & e)
    {
        RCLCPP_INFO(rclcpp::get_logger("OI"), "Exception %s", e.what());
        return false;
    } catch (...)
    {
        RCLCPP_INFO(rclcpp::get_logger("OI"), "Exception !!!");
        return false;
    }
    return false;
}

bool OIInference::post_process_image(const cv::Mat input, rvc_vision_messages::msg::RotatedBBList & rotatedBBList)
{
    std::vector<int> class_ids;
    std::vector<float> confidences;
    std::vector<cv::Rect> boxes;

    double confidence;
    cv::Point class_id_point;

    //filter out any detections below the object detected threshold
    for (int r = 0; r < input.rows; ++r)
    {
        //yolov5 or v6:
        if (model_version < 8)
        {
            cv::Mat class_scores = input.row(r).colRange(5, input.cols);
            double max_confidence;
            cv::minMaxLoc(class_scores, 0, &max_confidence, 0, &class_id_point);

            float object_confidence = input.at<float>(r, 4);
            //confidence = object_confidence*max_confidence;
            confidence = object_confidence;
        }
        else
        {
            //yolov8:
            RCLCPP_INFO(rclcpp::get_logger("OI"), " YOLOV8: minMax... %d", model_version);
            cv::Mat class_scores = input.row(r).colRange(4, input.cols);
            cv::Point class_id_point;
            cv::minMaxLoc(class_scores, 0, &confidence, 0, &class_id_point);
        }

        if (confidence > confidence_threshold)
        {
            int cx = input.at<float>(r, 0);
            int cy = input.at<float>(r, 1);
            int w = input.at<float>(r, 2);
            int h = input.at<float>(r, 3);
            boxes.push_back(cv::Rect(cx, cy, w, h));
            confidences.push_back(confidence);
            class_ids.push_back(class_id_point.x);
        }
    }

    std::vector<int> indices;
    cv::dnn::NMSBoxes(boxes, confidences, confidence_threshold, nms_threshold, indices);

    for (size_t i = 0; i < indices.size(); ++i)
    {
        rvc_vision_messages::msg::RotatedBB bb;
        int idx = indices[i];
        bb.cx = (boxes[idx].x / m_ratio) - m_pad_width;
        bb.cy = (boxes[idx].y / m_ratio) - m_pad_height;
        bb.width = boxes[idx].width / m_ratio;
        bb.height = boxes[idx].height / m_ratio;
        bb.angle = 0.0;
        bb.object_id = class_name_array_param[class_ids[idx]];
        bb.confidence_level = confidences[idx];
        rotatedBBList.rotated_bb_list.push_back(bb);
    }

    frameRate++;
    auto endTime = std::chrono::high_resolution_clock::now();
    static unsigned secondCount = 0;

    if ((endTime - startTime) > std::chrono::seconds(1))
    {
        secondCount++;

        RCLCPP_INFO(
            rclcpp::get_logger("OI"), "average FPS %f frames %d seconds %d",
            frameRate / (float)secondCount, frameRate, secondCount);
        startTime = endTime;

    }

    return true;
}

} //namespace RVC_AI
#include <pluginlib/class_list_macros.hpp>

PLUGINLIB_EXPORT_CLASS(RVC_AI::OIInference, RVC_AI::RVCAIInterface)
