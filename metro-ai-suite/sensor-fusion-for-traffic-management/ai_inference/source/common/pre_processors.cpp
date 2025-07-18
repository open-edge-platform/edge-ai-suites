/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2022 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#include "common/pre_processors.h"
#include "inference_nodes/base/image_inference_instance.hpp"

#include <algorithm>
#include <map>
#include <string>
#include <vector>

#include <opencv2/imgproc.hpp>

#include "common/pre_processor_info_parser.hpp"
#include "common/pre_processors.h"
#include "common/region_of_interest.h"
#include "utils.h"
namespace hce{

namespace ai{

namespace inference{
// using namespace InferenceBackend;

// namespace {



// } // anonymous namespace

// std::map<std::string, InputLayerDesc::Ptr>
//     ImageInferenceInstance::GetInputPreprocessors(const std::shared_ptr<InferenceBackend::ImageInference> &inference,
//                           const std::vector<ModelInputInfo::Ptr> &model_input_processor_info,const VideoRegionOfInterestMeta &roi) {
//     std::map<std::string, InferenceBackend::InputLayerDesc::Ptr> preprocessors;
//     for (const ModelInputInfo::Ptr &preproc : model_input_processor_info) {
//         preprocessors[preproc->format] = std::make_shared<InputLayerDesc>(InputLayerDesc());
//         preprocessors[preproc->format]->name = preproc->layer_name;
//         preprocessors[preproc->format]->preprocessor =
//             getInputPreprocFunctrByLayerType(preproc->format, inference, preproc->params, roi);

//         // define transform function to directly process InferenceBackend::InputBlob::Ptr
//         // preprocessors[preproc->format]->preprocessor = nullptr;

//         // support resize / crop etc. via model_proc json fields (only for format: image)
//         preprocessors[preproc->format]->input_image_preroc_params =
//             (preproc->format == "image") ? PreProcParamsParser(preproc->params).parse() : nullptr;
//     }
//     return preprocessors;
// }


// std::map<std::string, InputLayerDesc::Ptr>
// GetInputPreprocessors(const std::shared_ptr<InferenceBackend::ImageInference> &inference,
//                       const std::vector<ModelInputInfo::Ptr> &model_input_processor_info,
//                       GstVideoRegionOfInterestMeta *roi) {
//     // ITT_TASK(__FUNCTION__);
//     std::map<std::string, InferenceBackend::InputLayerDesc::Ptr> preprocessors;
//     for (const ModelInputProcessorInfo::Ptr &preproc : model_input_processor_info) {
//         preprocessors[preproc->format] = std::make_shared<InputLayerDesc>(InputLayerDesc());
//         preprocessors[preproc->format]->name = preproc->layer_name;
//         preprocessors[preproc->format]->preprocessor =
//             getInputPreprocFunctrByLayerType(preproc->format, inference, preproc->params, roi);

//         preprocessors[preproc->format]->input_image_preroc_params =
//             (preproc->format == "image") ? PreProcParamsParser(preproc->params).parse() : nullptr;
//     }
//     return preprocessors;
// }
}

}

}