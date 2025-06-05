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

#pragma once

#include "inference_backend/image_inference.h"

#include <nlohmann/json.hpp>

using PreProcResize = InferenceBackend::InputImageLayerDesc::Resize;
using PreProcCrop = InferenceBackend::InputImageLayerDesc::Crop;
using PreProcColorSpace = InferenceBackend::InputImageLayerDesc::ColorSpace;
using PreProcRangeNormalization = InferenceBackend::InputImageLayerDesc::RangeNormalization;
using PreProcDistribNormalization = InferenceBackend::InputImageLayerDesc::DistribNormalization;
using PreProcPadding = InferenceBackend::InputImageLayerDesc::Padding;

class PreProcParamsParser {
  private:
    const nlohmann::json params;

    PreProcParamsParser() = delete;

    PreProcResize getResize() const;
    PreProcCrop getCrop() const;
    PreProcColorSpace getColorSpace() const;
    PreProcRangeNormalization getRangeNormalization() const;
    PreProcDistribNormalization getDistribNormalization() const;
    PreProcPadding getPadding() const;

  public:
    PreProcParamsParser(const nlohmann::json params);
    InferenceBackend::InputImageLayerDesc::Ptr parse() const;
};
