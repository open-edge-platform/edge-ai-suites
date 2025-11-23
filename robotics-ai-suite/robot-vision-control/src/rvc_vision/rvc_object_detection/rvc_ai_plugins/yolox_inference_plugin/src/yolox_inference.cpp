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

#include "yolox_inference.hpp"


using namespace RVC_AI;


YoloxInference::YoloxInference() :
    confidence_threshold(0.7),
    nms_threshold(0.5)
{
    /** default values for 640x480 when model input is square. will be overwritten*/
    m_ratio = 1.0;
    m_pad_height = 80;
    m_pad_width = 0;
    frameRate = 30;
    m_resX = 640;
    m_resY = 480;
    m_input_shape_x = m_input_shape_y = 640;
    model_version = 5;
}

// TODO: check for failures
bool YoloxInference::init(rclcpp::Node *node, const std::string &modelName)
{
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
        RCLCPP_INFO(node->get_logger(), "Yolox plugin: Looking for OpenVino Model Files %s", xml_file.c_str());
    }


    model_version = model_version_param;

    RCLCPP_INFO(node->get_logger(), " OpenVINO yolox plugin: Model Version: %d", model_version);

    ov::AnyMap config{{ov::hint::performance_mode.name(), ov::hint::PerformanceMode::LATENCY},{"CACHE_DIR", "/rvc/cl_cache_dir"}};

    RCLCPP_INFO(node->get_logger(), "OpenVINO yolox plugin: loading Model %s", xml_file.c_str());

    try {
        model = core.read_model(xml_file);
    } catch (const std::exception& e) {
        RCLCPP_ERROR(node->get_logger(), "Failed to load model %s: %s", xml_file.c_str(), e.what());
        return false;
    }

    const std::vector<ov::Output<ov::Node>> inputs = model->inputs();

    for (const ov::Output<const ov::Node> input : inputs)
    {
        RCLCPP_INFO_STREAM(rclcpp::get_logger("Yolox"), "    inputs");

        const std::string name = input.get_names().empty() ? "NONE" : input.get_any_name();
        RCLCPP_INFO_STREAM(rclcpp::get_logger("Yolox"), "        input name: " << name);

        const ov::element::Type type = input.get_element_type();
        RCLCPP_INFO_STREAM(rclcpp::get_logger("Yolox"), "        input type: " << type);

    }

  //RESHAPE batch
  std::map<ov::Output<ov::Node>, ov::PartialShape> port_to_shape;

  auto fingerShape = inputs[0].get_partial_shape();
  fingerShape[0] = 1;
  
  port_to_shape[inputs[0]] = fingerShape;
  model->reshape(port_to_shape);


  m_input_shape_x =  inputs[0].get_shape()[3];
  m_input_shape_y =  inputs[0].get_shape()[2];
  RCLCPP_INFO_STREAM(rclcpp::get_logger("Yolox"),
                     "        input shape (reshaped): " <<  inputs[0].get_shape());

  m_pad_width = (resx_param - resy_param) / 2;
  m_pad_height = 0;

    ov::preprocess::PrePostProcessor ppp(model);
    ov::preprocess::InputInfo & input_info = ppp.input();

    //auto squared_size = resx_param > resy_param ? resx_param : resy_param;
    input_info.tensor()
        .set_element_type(ov::element::u8)
        .set_layout("NHWC")
        .set_color_format(ov::preprocess::ColorFormat::BGR)        
        .set_spatial_static_shape(m_resX, m_resX);

    input_info.model().set_layout("NCHW");
    input_info.preprocess()
        .convert_element_type(ov::element::f32)
        .convert_color(ov::preprocess::ColorFormat::RGB)
        .resize(ov::preprocess::ResizeAlgorithm::RESIZE_LINEAR, m_input_shape_y, m_input_shape_x);
    model = ppp.build();

    RCLCPP_INFO_STREAM(rclcpp::get_logger("Yolox"), " PREPROC: " << ppp);

    try {
        compiledModel = core.compile_model(model, inference_device, config);
    } catch (const std::exception& e) {
        RCLCPP_ERROR(node->get_logger(), "Failed to compile model for device %s: %s", inference_device.c_str(), e.what());
        return false;
    }

    uint32_t nireq = compiledModel.get_property(ov::optimal_number_of_infer_requests);

    RCLCPP_INFO(rclcpp::get_logger("Yolox"), "optimal_number_of_infer_requests: %d", nireq);

    for (uint32_t i = 0; i < nireq; ++i)
    {
        idleRequests.push(compiledModel.create_infer_request());
    }

    const std::vector<ov::Output<ov::Node>> outputs = model->outputs();

    for (auto o : outputs) {
        RCLCPP_INFO_STREAM(rclcpp::get_logger("BS"),
                       "        outputs name: " << o.get_any_name());
        RCLCPP_INFO_STREAM(rclcpp::get_logger("BS"),
                       "        outputs type: " << o.get_element_type());

        std::map<ov::Output<ov::Node>, ov::PartialShape> port_to_shape;
        auto partialShape = o.get_partial_shape();
        port_to_shape[o] = partialShape;

        RCLCPP_INFO_STREAM(rclcpp::get_logger("BS"), "        fingerOutputs shape: " << o.get_partial_shape());
   
    }


    startTime = std::chrono::high_resolution_clock::now();
    return true;
}

bool YoloxInference::pre_process_image(const cv::Mat inputImage, cv::Mat & outputImage)
{

    cv::Mat nn_input_blob, nn_output;
    cv::Mat output;

    static cv::Size nn_input_size(m_input_shape_x, m_input_shape_y);
    static constexpr int YOLOX_PAD_VALUE = 114;  // YOLOX standard padding value
    static cv::Scalar border_color(YOLOX_PAD_VALUE, YOLOX_PAD_VALUE, YOLOX_PAD_VALUE);

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

bool YoloxInference::run_inference_pipeline(const cv::Mat input, cv::Mat & outputImage)
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
            ov::Tensor output_tensor_boxes = infer_request.get_output_tensor(0);
            ov::Tensor  output_tensor_labels = infer_request.get_output_tensor(1);
            infer_request.set_callback(
                [&infer_request, &output_tensor_boxes, &output_tensor_labels, this](std::exception_ptr ex)
                {
                    (void)ex;
                    std::unique_lock<std::mutex> lock(idleRequestsMutex);
                    idleRequests.push(infer_request);
                    output_tensor_boxes = infer_request.get_output_tensor(0);
                    output_tensor_labels = infer_request.get_output_tensor(1);
                    idleRequestsCV.notify_one();
                });

            auto input_tensor = ov::Tensor(
                infer_request.get_input_tensor().get_element_type(),
                infer_request.get_input_tensor().get_shape(), input.data);

            infer_request.set_input_tensor(input_tensor);

            infer_request.start_async();
            infer_request.wait();


            auto shape_boxes = output_tensor_boxes.get_shape();
            auto shape_labels = output_tensor_labels.get_shape();

            size_t num_boxes = shape_boxes[1];
            size_t box_attrs = shape_boxes[2];
    
            cv::Mat boxes_float(num_boxes, box_attrs, CV_32F,(void *)output_tensor_boxes.data<float>());

            size_t num_labels = shape_labels.size() >= 2 ? shape_labels[1] : shape_labels[0];
            cv::Mat labels_float(num_labels, 1, CV_32F);
            {
                auto *lbl_ptr = output_tensor_labels.data<int64_t>();
                for (size_t i = 0; i < num_labels; ++i)
                {
                    //RCLCPP_INFO(rclcpp::get_logger("Yolox"), "Label[%zu] = %ld", i, lbl_ptr[i]);
                    labels_float.at<float>(i, 0) = static_cast<float>(lbl_ptr[i]);
                }
            }
    
            if (labels_float.rows != boxes_float.rows)
            {
                RCLCPP_ERROR(rclcpp::get_logger("Yolox"), "YOLOX output mismatch: boxes=%d labels=%d",
                        boxes_float.rows, labels_float.rows);
                return false;
            }
            else
            {
                // Merge: [x y w h cls]
                cv::Mat merged;
                cv::hconcat(boxes_float, labels_float, merged);
                outputImage = std::move(merged);
                return true;
            }
        }
    } catch (const std::exception& e)
    {
        RCLCPP_ERROR(rclcpp::get_logger("Yolox"), "Inference failed: %s", e.what());
        return false;
    } catch (...)
    {
        RCLCPP_ERROR(rclcpp::get_logger("Yolox"), "Inference failed with unknown exception");
        return false;
    }
    return false;
}

bool YoloxInference::post_process_image(const cv::Mat input, rvc_vision_messages::msg::RotatedBBList & rotatedBBList)
{
    std::vector<int> class_ids;
    std::vector<float> confidences;
    std::vector<cv::Rect> boxes;

    double confidence;
    cv::Point class_id_point;

    //filter out any detections below the object detected threshold
    for (int r = 0; r < input.rows; ++r)
    {
        int chosen_class = 0;

        chosen_class = static_cast<int>(round(input.at<float>(r, 5))); // safer cast

        confidence = input.at<float>(r, 4);

	    if (confidence > confidence_threshold)
        {
            float x = input.at<float>(r, 0);
            float y = input.at<float>(r, 1);
            float w = input.at<float>(r, 2)-x;
            float h = input.at<float>(r, 3)-y;
            boxes.push_back(cv::Rect(cv::Point((int)x, (int)y), cv::Size((int)w, (int)h)));

            confidences.push_back(confidence);
            class_ids.push_back(chosen_class);
        }
    }

    std::vector<int> indices;
    cv::dnn::NMSBoxes(boxes, confidences, confidence_threshold, nms_threshold, indices);

    for (size_t i = 0; i < indices.size(); ++i)
    {
        rvc_vision_messages::msg::RotatedBB bb;
        int idx2 = indices[i];
        bb.cx = ((boxes[idx2].x + (boxes[idx2].width/2.0)) / m_ratio) - m_pad_width;
        bb.cy = ((boxes[idx2].y + (boxes[idx2].height/2.0))/ m_ratio) - m_pad_height;

        bb.width = boxes[idx2].width / m_ratio;
        bb.height = boxes[idx2].height / m_ratio;
        bb.angle = 0.0;
        bb.object_id = class_name_array_param[class_ids[idx2]];
        bb.confidence_level = confidences[idx2];
        rotatedBBList.rotated_bb_list.push_back(bb);
    }

    frameRate++;
    auto endTime = std::chrono::high_resolution_clock::now();
    static unsigned secondCount = 0;

    if ((endTime - startTime) > std::chrono::seconds(1))
    {
        secondCount++;

        RCLCPP_DEBUG(
            rclcpp::get_logger("Yolox"), "Average FPS %f frames %d seconds %d",
            frameRate / (float)secondCount, frameRate, secondCount);
        startTime = endTime;

    }
    return true;
}


#include <pluginlib/class_list_macros.hpp>

PLUGINLIB_EXPORT_CLASS(RVC_AI::YoloxInference, RVC_AI::RVCAIInterface)
