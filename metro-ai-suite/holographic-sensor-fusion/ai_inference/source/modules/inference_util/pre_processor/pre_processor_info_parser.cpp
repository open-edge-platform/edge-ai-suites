/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2024 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#include "modules/inference_util/pre_processor/pre_processor_info_parser.hpp"

#include <cassert>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

PreProcParamsParser::PreProcParamsParser(const nlohmann::json params) : params(params) {
}

InferenceBackend::InputImageLayerDesc::Ptr PreProcParamsParser::parse() const {
    if (params.empty()) {
        return nullptr;
    }

    const auto resize = getResize();
    const auto crop = getCrop();

    const auto color_space = getColorSpace();
    const auto range_norm = getRangeNormalization();
    const auto distrib_norm = getDistribNormalization();

    const auto padding = getPadding();

    return std::make_shared<InferenceBackend::InputImageLayerDesc>(
        InferenceBackend::InputImageLayerDesc(resize, crop, color_space, range_norm, distrib_norm, padding));
}

PreProcResize PreProcParamsParser::getResize() const {
    PreProcResize resize_val = PreProcResize::NO;

    if (params.find("resize") != params.cend()) {
        std::string resize_type = params["resize"].get<std::string>();
        if (resize_type == "aspect-ratio") {
            resize_val = PreProcResize::ASPECT_RATIO;
        } else if (resize_type == "no-aspect-ratio") {
            resize_val = PreProcResize::NO_ASPECT_RATIO;
        } else {
            throw std::runtime_error(std::string("Invalid type of resize: ") + resize_type);
        }
    }

    return resize_val;
}

PreProcCrop PreProcParamsParser::getCrop() const {
    PreProcCrop crop_val = PreProcCrop::NO;

    if (params.find("crop") != params.cend()) {
        std::string crop_type = params["crop"].get<std::string>();
        if (crop_type == "central") {
            crop_val = PreProcCrop::CENTRAL;
        } else if (crop_type == "top_left") {
            crop_val = PreProcCrop::TOP_LEFT;
        } else if (crop_type == "top_right") {
            crop_val = PreProcCrop::TOP_RIGHT;
        } else if (crop_type == "bottom_left") {
            crop_val = PreProcCrop::BOTTOM_LEFT;
        } else if (crop_type == "bottom_right") {
            crop_val = PreProcCrop::BOTTOM_RIGHT;
        } else {
            throw std::runtime_error(std::string("Invalid type of crop: ") + crop_type);
        }
    }
    return crop_val;
}

PreProcColorSpace PreProcParamsParser::getColorSpace() const {
    PreProcColorSpace color_space_val = PreProcColorSpace::NO;
    
    if (params.find("color_space") != params.cend()) {
        std::string color_space_type = params["color_space"].get<std::string>();
        if (color_space_type == "RGB") {
            color_space_val = PreProcColorSpace::RGB;
        } else if (color_space_type == "BGR") {
            color_space_val = PreProcColorSpace::BGR;
        } else if (color_space_type == "YUV") {
            color_space_val = PreProcColorSpace::YUV;
        } else if (color_space_type == "GRAYSCALE") {
            color_space_val = PreProcColorSpace::GRAYSCALE;
        } else {
            throw std::runtime_error(std::string("Invalid target color format: ") + color_space_type);
        }
    }
    return color_space_val;
}

PreProcRangeNormalization PreProcParamsParser::getRangeNormalization() const {

    std::vector<double> range;
    try {
        if (params.find("range") != params.cend()) {
            range = params["range"].get<std::vector<double>>();
            if (range.size() != 2)
                throw std::runtime_error("Invalid \"range\" array in model-proc file. It should only contain two "
                                            "values (minimum and maximum)");
            return PreProcRangeNormalization(range[0], range[1]);
        }
    } catch (const std::exception &e) {
        std::throw_with_nested(std::runtime_error("Error during \"range\" structure parse. (error: " + std::string(e.what()) + ")"));
    }
    
    return PreProcRangeNormalization();
}

PreProcDistribNormalization PreProcParamsParser::getDistribNormalization() const {

    std::vector<double> mean, std;
    if (params.find("mean") != params.cend() &&
        params.find("std") != params.cend()) {
        mean = params["mean"].get<std::vector<double>>();
        std = params["std"].get<std::vector<double>>();
        return PreProcDistribNormalization(mean, std);
    }
    return PreProcDistribNormalization();
}

PreProcPadding PreProcParamsParser::getPadding() const {
    nlohmann::json padding = params.value("padding", nlohmann::json());

    try {
        if (params.find("padding") != params.cend()) {
            nlohmann::json padding = params["padding"];

            if (padding.find("stride") != padding.cend() &&
                (padding.find("stride_x") != padding.cend() || padding.find("stride_y") != padding.cend())) {
                    throw std::runtime_error("Padding structure has duplicated information about stride.");
            }

            // get padding info
            size_t stride_x = 0;
            size_t stride_y = 0;
            if (padding.find("stride") != padding.cend()) {
                size_t stride = padding["stride"].get<int>();
                stride_x = stride;
                stride_y = stride;
            }
            else {
                if (padding.find("stride_x") != padding.cend())
                    stride_x = padding["stride_x"].get<int>();
                if (padding.find("stride_y") != padding.cend())
                    stride_y = padding["stride_y"].get<int>();
            }

            std::vector<double> fill_value(3, 0);
            if (padding.find("fill_value") != padding.cend()) {
                fill_value = padding["fill_value"].get<std::vector<double>>();
            }
            return PreProcPadding(stride_x, stride_y, fill_value);
        }
    } catch (const std::exception &e) {
        std::throw_with_nested(std::runtime_error("Error during \"padding\" structure parse. (error: " + std::string(e.what()) + ")"));
    }

    return PreProcPadding{};
}
