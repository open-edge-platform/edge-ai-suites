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

#ifndef __IMAGE_INFERENCE_INSTANCE_HPP__
#define __IMAGE_INFERENCE_INSTANCE_HPP__

#include <map>
#include <gst/video/gstvideometa.h>
#include <inc/api/hvaBlob.hpp>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>

#include "utils.h"
#include "common/context.h"
#include "common/common.hpp"

#include "nodes/databaseMeta.hpp"
#include "inference_backend/buffer_mapper.h"
#include "modules/inference_util/model_proc/model_proc_provider.hpp"
#include "modules/inference_util/model_proc/model_preproc.h"
#include "modules/inference_util/pre_processor/pre_processor_info_parser.hpp"

#include "inference_backend/image_inference.h"
#include "inference_backend/pre_proc.h"

using namespace InferenceBackend;

namespace hce{

namespace ai{

namespace inference{

using InputLayerDesc = InferenceBackend::InputLayerDesc;
using ImagePreprocessorType = InferenceBackend::ImagePreprocessorType;
using InferenceConfig = InferenceBackend::InferenceConfig;
using MemoryType = InferenceBackend::MemoryType;
using Allocator = InferenceBackend::Allocator;

typedef enum { 
    HVA_DETECTION_TYPE = 0, 
    HVA_CLASSIFICATION_TYPE,
    HVA_REGRESSION_TYPE, 
    HVA_FEATURE_EXTRACTION_TYPE,
    HVA_NONE_TYPE                       // do not use DL Inference
} InferenceType;

typedef enum { FULL_FRAME = 0, ROI_LIST } InferenceRegionType;

struct VideoRegionOfInterestMeta {

    int roi_id;

    int x;
    int y;
    int width;
    int height;

    VideoRegionOfInterestMeta(): x(0), y(0), width(0), height(0), roi_id(0) {};
    VideoRegionOfInterestMeta(int x, int y, int width, int height, int id): 
        x(x), y(y), width(width), height(height), roi_id(id) {};
    ~VideoRegionOfInterestMeta() {};

};

typedef struct _InferenceProperty {

    // properties
    std::string device;
    int device_id;
    std::string device_extensions;                  // "device1=extension1,device2=extension2"-like string
    std::string model_path;
    std::string model_proc_config;
    std::string model_proc_lib;
    unsigned int inference_interval;
    unsigned int nireq;                             // infer request number
    unsigned int batch_size;

    std::vector<std::string> inference_config;

    std::string pre_proc_type;                      // options: ["", "ie", "vaapi", "vaapi-surface-sharing", "opencv"]
    std::vector<std::string> pre_proc_config;
    std::string allocator_name;

    InferenceType inference_type;
    InferenceRegionType inference_region_type;

    bool reshape_model_input;                       // reshape_width > 0 OR  reshape_height > 0 OR batch_size > 1
                                                        // can all affect `reshape_model_input`
    unsigned int reshape_width;
    unsigned int reshape_height;
    unsigned int image_width;
    unsigned int image_height;

} InferenceProperty;

struct InferenceFrame {
    VideoRegionOfInterestMeta roi;

    InferenceBackend::ImageTransformationParams::Ptr image_transform_info = nullptr;

    InferenceFrame() = default;
    InferenceFrame(const InferenceFrame &) = delete;
    InferenceFrame &operator=(const InferenceFrame &rhs) = delete;
    ~InferenceFrame() = default;
};

enum InferenceStatus {
    INFERENCE_NONE = 0,
    INFERENCE_EXECUTED = 1,
    INFERENCE_SKIPPED_ROI = 2           // roi skipped because all input rois should be ignored
};


class ImageInferenceInstance {
public:
    using Ptr = std::shared_ptr<ImageInferenceInstance>;

    struct Model {
        std::string name;
        std::shared_ptr<InferenceBackend::ImageInference> inference;
        std::vector<ModelInputInfo::Ptr> input_processor_info;
        // std::map<std::string, GstStructure *> output_processor_info;
        // std::string labels;
    };

    ImageInferenceInstance(InferenceProperty& inference_property);

    ~ImageInferenceInstance();

    /**
     * @brief set callback function
     * @param func callback function for inference success case
     * @param func1 callback function for inference fail case
     * 
    */
    void SetCallbackFunc(
        InferenceBackend::ImageInference::CallbackFunc func,
        InferenceBackend::ImageInference::ErrorHandlingFunc func1);

    void CreateModel(InferenceProperty& inference_property);

    void FlushInference();

    InferenceStatus SubmitInference(const InferenceProperty& inference_property, hva::hvaBlob_t::Ptr& input);

    struct InferenceResult : public InferenceBackend::ImageInference::IFrameBase {
        void SetImage(InferenceBackend::ImagePtr image_) override {
            image = image_;
        }
        InferenceBackend::ImagePtr GetImage() const override {
            return image;
        }
        std::shared_ptr<InferenceFrame> inference_frame;
        Model *model;
        std::shared_ptr<InferenceBackend::Image> image;
        hva::hvaBlob_t::Ptr input;
        size_t region_count;
    };

private:

    Model m_model;
    std::shared_ptr<InferenceBackend::Allocator> m_allocator;

    MemoryType m_memory_type;
    std::unique_ptr<InferenceBackend::BufferToImageMapper> m_buffer_mapper;

    InferenceBackend::ImageInference::CallbackFunc m_callback_func;
    InferenceBackend::ImageInference::ErrorHandlingFunc m_callback_func_error_handle;

    InferenceStatus SubmitImages(const InferenceProperty& inference_property,
                      const std::vector<VideoRegionOfInterestMeta>& metas,
                      hva::hvaBlob_t::Ptr& input);

    inline std::shared_ptr<Allocator> CreateAllocator(const std::string allocator_name);

    unsigned int GetOptimalBatchSize(std::string device);

    void UpdateModelReshapeInfo(InferenceProperty& inference_property);

    InferenceBackend::InferenceConfig CreateNestedInferenceConfig(InferenceProperty& inference_property);

    ImagePreprocessorType ImagePreprocessorTypeFromString(const std::string &image_preprocessor_name);

    void UpdateConfigWithLayerInfo(
        const std::vector<ModelInputInfo::Ptr>& model_input_processor_info,
        InferenceConfig& config);

    // MemoryType GetMemoryType(MemoryType input_image_memory_type, ImagePreprocessorType image_preprocessor_type);

    void ApplyImageBoundaries(std::shared_ptr<InferenceBackend::Image>& image,
                              const VideoRegionOfInterestMeta& rois,
                              InferenceRegionType inference_region);

    std::shared_ptr<ImageInferenceInstance::InferenceResult>
    MakeInferenceResult(const InferenceProperty& inference_property, Model &model, 
                        const VideoRegionOfInterestMeta& meta,
                        std::shared_ptr<InferenceBackend::Image> &image,
                        hva::hvaBlob_t::Ptr input);
        
    std::map<std::string, InputLayerDesc::Ptr>
    // GetInputPreprocessors(const std::shared_ptr<InferenceBackend::ImageInference> &inference,
    //                       const std::vector<ModelInputInfo::Ptr> &model_input_processor_info);

    GetInputPreprocessors(const std::shared_ptr<InferenceBackend::ImageInference> &inference,
                          const std::vector<ModelInputInfo::Ptr> &model_input_processor_info, const VideoRegionOfInterestMeta &roi);
    /**
     * @brief Retrieves the input preprocessors for image inference.
     *
     * This function retrieves the input preprocessors for image inference based on the provided parameters.
     *
     * @param inference The shared pointer to the ImageInference object.
     * @param model_input_processor_info The vector of ModelInputInfo pointers containing information about the model input processors.
     * @param roi The GstVideoRegionOfInterestMeta object representing the region of interest.
     * 
     * @return The input preprocessors for image inference.
     */
    // GetInputPreprocessors(const std::shared_ptr<InferenceBackend::ImageInference> &inference,
    //                   const std::vector<ModelInputInfo::Ptr> &model_input_processor_info, GstVideoRegionOfInterestMeta *roi);
};

} // namespace inference

} // namespace ai

} // namespace hce

#endif /*__IMAGE_INFERENCE_INSTANCE_HPP__*/
