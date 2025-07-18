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

#include "inference_nodes/base/image_inference_instance.hpp"
#include "common/pre_processors.h"


#include <algorithm>
#include <map>
#include <string>
#include <vector>

#include <opencv2/imgproc.hpp>

#include "modules/inference_util/pre_processor/pre_processor_info_parser.hpp"
#include "common/pre_processors.h"
#include "common/region_of_interest.h"
#include "utils.h"
#ifdef ENABLE_VAAPI
    #include "vaapi_utils.h"
    #include "va_device_manager.h"
// #include "image_inference_instance.hpp"
#endif

namespace hce{

namespace ai{

namespace inference{

ImageInferenceInstance::ImageInferenceInstance(InferenceProperty& inference_property) {

    // check model path
    if (inference_property.model_path.empty()) {
        throw std::runtime_error("Create inference instance error: model not specified");
    }
    // check model file path
    if (!Utils::fileExists(inference_property.model_path))
        throw std::invalid_argument("Model file '" + inference_property.model_path + "' does not exist");

    m_allocator = CreateAllocator(inference_property.allocator_name);

    m_callback_func = nullptr;
    m_callback_func_error_handle = nullptr;
}

ImageInferenceInstance::~ImageInferenceInstance() {

}

/**
 * @brief set callback function
 * @param func callback function if inference success
 * @param func1 callback function if inference failed
 * 
*/
void ImageInferenceInstance::SetCallbackFunc(
    InferenceBackend::ImageInference::CallbackFunc func,
    InferenceBackend::ImageInference::ErrorHandlingFunc func1) {
    m_callback_func = func;
    m_callback_func_error_handle = func1;
}

/**
 * @brief submit inference to specific InferenceBackend (OpenVINO, etc.)
 * @param inference_property
 * @param input
 * @return inference status
*/
InferenceStatus ImageInferenceInstance::SubmitInference(const InferenceProperty& inference_property, hva::hvaBlob_t::Ptr& input) {

    if (!m_buffer_mapper)
        throw std::invalid_argument("Buffer Mapper is null");
    hva::hvaVideoFrameWithROIBuf_t::Ptr buffer = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(input->get(0));

    /* Collect all ROI metas into std::vector */
    std::vector<VideoRegionOfInterestMeta> metas;
    HVA_DEBUG("ImageInferenceInstance::SubmitInference collectROIMetas");
    HVA_INFO("inference_region_type %d",inference_property.inference_region_type);
    switch (inference_property.inference_region_type) {
        case ROI_LIST: {
            /* iterates through buffer's meta and pushes it in vector if inference needed. */
            
            // handle `ignore` flag here
            hce::ai::inference::HceDatabaseMeta inputMeta;
            buffer->getMeta(inputMeta);
            for (size_t roi_id = 0; roi_id < buffer->rois.size(); roi_id ++) {
                auto roi = buffer->rois[roi_id];
                if (inputMeta.ignoreFlags.count(roi_id) > 0 && inputMeta.ignoreFlags[roi_id] == true) {
                    // should be ignored in this inference
                    // do nothing
                }
                else {
                    VideoRegionOfInterestMeta meta(roi.x, roi.y, roi.width, roi.height, roi_id);
                    metas.push_back(meta);
                }
                
            }
            break;
        }
        case FULL_FRAME: {
            /* pushes single meta in vector if full-frame inference is invoked. */
            HVA_INFO("buffer->width: %d", buffer->width);
            HVA_INFO("buffer->height: %d", buffer->height);
            VideoRegionOfInterestMeta full_frame_meta(0, 0, buffer->width, buffer->height, 0);
            metas.push_back(full_frame_meta);
            break;
        }
        default:
            throw std::logic_error("Unsupported inference region type");
    }

    if (metas.empty()) {
        // nothing to be inferenced
        return InferenceStatus::INFERENCE_SKIPPED_ROI;
    }
    HVA_INFO("SubmitImages start.");
    return SubmitImages(inference_property, metas, input);

}

GstVideoRegionOfInterestMeta* ConvertToGstMeta(const VideoRegionOfInterestMeta& meta) {
    GstVideoRegionOfInterestMeta* gstMeta = new GstVideoRegionOfInterestMeta();
    gstMeta->x = meta.x;
    gstMeta->y = meta.y;
    gstMeta->w = meta.width;
    gstMeta->h = meta.height;
    gstMeta->id = meta.roi_id;

    return gstMeta;
}
InputPreprocessingFunction createImageInfoFunction(const GstStructure *params, const ImageInference::Ptr &inference) {
    double scale = 1.0;
    gst_structure_get_double(params, "scale", &scale);

    size_t width = 0;
    size_t height = 0;
    size_t batch = 0;
    int format = 0;
    int memory_type = 0;
    inference->GetModelImageInputInfo(width, height, batch, format, memory_type);

    return [width, height, scale](const InputBlob::Ptr &blob) {
        auto dims = blob->GetDims();
        float *data = reinterpret_cast<float *>(blob->GetData());
        data[0] = static_cast<float>(height);
        data[1] = static_cast<float>(width);
        std::fill(data + 2, data + dims[1], static_cast<float>(scale));
    };
}

InputPreprocessingFunction createSequenceIndexFunction() {
    return [](const InputBlob::Ptr &blob) {
        size_t maxSequenceSizePerPlate = blob->GetDims()[0];
        float *blob_data = reinterpret_cast<float *>(blob->GetData());
        std::fill(blob_data, blob_data + maxSequenceSizePerPlate, 1.0f);
    };
}

cv::Mat getTransform(cv::Mat *src, cv::Mat *dst) {
    if (not src or not dst)
        throw std::invalid_argument("Invalid cv::Mat inputs for GetTransform");
    cv::Mat col_mean_src;
    reduce(*src, col_mean_src, 0, cv::REDUCE_AVG);
    for (int i = 0; i < src->rows; i++) {
        src->row(i) -= col_mean_src;
    }

    cv::Mat col_mean_dst;
    reduce(*dst, col_mean_dst, 0, cv::REDUCE_AVG);
    for (int i = 0; i < dst->rows; i++) {
        dst->row(i) -= col_mean_dst;
    }

    cv::Scalar mean, dev_src, dev_dst;
    cv::meanStdDev(*src, mean, dev_src);
    dev_src(0) = std::max(static_cast<double>(std::numeric_limits<float>::epsilon()), dev_src(0));
    *src /= dev_src(0);
    cv::meanStdDev(*dst, mean, dev_dst);
    dev_dst(0) = std::max(static_cast<double>(std::numeric_limits<float>::epsilon()), dev_dst(0));
    *dst /= dev_dst(0);

    cv::Mat w, u, vt;
    cv::SVD::compute((*src).t() * (*dst), w, u, vt);
    cv::Mat r = (u * vt).t();
    cv::Mat m(2, 3, CV_32F);
    m.colRange(0, 2) = r * (dev_dst(0) / dev_src(0));
    m.col(2) = (col_mean_dst.t() - m.colRange(0, 2) * col_mean_src.t());
    return m;
}

void alignRgbImage(Image &image, const std::vector<float> &landmarks_points,
                   const std::vector<float> &reference_points) {
    cv::Mat ref_landmarks = cv::Mat(reference_points.size() / 2, 2, CV_32F);
    cv::Mat landmarks =
        cv::Mat(landmarks_points.size() / 2, 2, CV_32F, const_cast<float *>(&landmarks_points.front())).clone();
    for (int i = 0; i < ref_landmarks.rows; i++) {
        ref_landmarks.at<float>(i, 0) = reference_points[2 * i] * image.width;
        ref_landmarks.at<float>(i, 1) = reference_points[2 * i + 1] * image.height;
        landmarks.at<float>(i, 0) *= image.width;
        landmarks.at<float>(i, 1) *= image.height;
    }
    cv::Mat m = getTransform(&ref_landmarks, &landmarks);
    for (int plane_num = 0; plane_num < 4; plane_num++) {
        if (image.planes[plane_num]) {
            cv::Mat mat0(image.height, image.width, CV_8UC1, image.planes[plane_num], image.stride[plane_num]);
            cv::warpAffine(mat0, mat0, m, mat0.size(), cv::WARP_INVERSE_MAP);
        }
    }
}

Image getImage(const InputBlob::Ptr &blob) {
    Image image = Image();

    auto dims = blob->GetDims();
    auto layout = blob->GetLayout();
    switch (layout) {
    case InputBlob::Layout::NCHW:
        image.height = dims[2];
        image.width = dims[3];
        break;
    case InputBlob::Layout::NHWC:
        image.height = dims[1];
        image.width = dims[2];
        break;
    default:
        throw std::invalid_argument("Unsupported layout for image");
    }
    uint8_t *data = reinterpret_cast<uint8_t *>(blob->GetData());
    data += blob->GetIndexInBatch() * 3 * image.width * image.height;
    image.planes[0] = data;
    image.planes[1] = data + image.width * image.height;
    image.planes[2] = data + 2 * image.width * image.height;
    image.planes[3] = nullptr;

    image.stride[0] = image.stride[1] = image.stride[2] = image.stride[3] = image.width;

    image.format = FourCC::FOURCC_RGBP;
    return image;
}

InputPreprocessingFunction createFaceAlignmentFunction(GstStructure *params, GstVideoRegionOfInterestMeta *roi_meta) {
    std::vector<float> reference_points;
    std::vector<float> landmarks_points;
    // look for tensor data with corresponding format
    RegionOfInterest roi(roi_meta);
    for (auto tensor : roi.tensors()) {
        if (tensor.format() == "landmark_points") {
            landmarks_points = tensor.data<float>();
            break;
        }
    }
    // load reference points from JSON input_preproc description
    GValueArray *alignment_points = nullptr;
    if (params and gst_structure_get_array(params, "alignment_points", &alignment_points)) {
        for (size_t i = 0; i < alignment_points->n_values; i++) {
            reference_points.push_back(g_value_get_double(alignment_points->values + i));
        }
        G_GNUC_BEGIN_IGNORE_DEPRECATIONS
        g_value_array_free(alignment_points);
        G_GNUC_END_IGNORE_DEPRECATIONS
    }

    if (landmarks_points.size() and landmarks_points.size() == reference_points.size()) {
        return [reference_points, landmarks_points](const InputBlob::Ptr &blob) {
            Image image = getImage(blob);
            alignRgbImage(image, landmarks_points, reference_points);
        };
    }
    return [](const InputBlob::Ptr &) {};
}

InputPreprocessingFunction createImageInputFunction(GstStructure *params, GstVideoRegionOfInterestMeta *roi) {
    return createFaceAlignmentFunction(params, roi);
}

InputPreprocessingFunction getInputPreprocFunctrByLayerType(const std::string &format,
                                                            const ImageInference::Ptr &inference,
                                                            nlohmann::json preproc_params,
                                                            GstVideoRegionOfInterestMeta *roi) {
                                                           
    GstStructure* gst_params = gst_structure_new_empty("VideoProcessingParams");

    if (preproc_params.contains("scale") && preproc_params["scale"].is_number()) {
        double scale = preproc_params["scale"];
        gst_structure_set(gst_params, "scale", G_TYPE_DOUBLE, scale, NULL);
    }

    if (preproc_params.contains("offset") && preproc_params["offset"].is_number()) {
        int offset = preproc_params["offset"];
        gst_structure_set(gst_params, "offset", G_TYPE_INT, offset, NULL);
    }
    InputPreprocessingFunction result;
    if (format == "sequence_index")
        result = createSequenceIndexFunction();
    else if (format == "image_info")
        result = createImageInfoFunction(gst_params, inference);
    else
        result = createImageInputFunction(gst_params, roi);

    return result;
}
InferenceStatus ImageInferenceInstance::SubmitImages(const InferenceProperty& inference_property, 
                                     const std::vector<VideoRegionOfInterestMeta>& metas, 
                                     hva::hvaBlob_t::Ptr& input) {
    
    InferenceStatus status = InferenceStatus::INFERENCE_NONE;

    try {
        if (!m_buffer_mapper)
            throw std::invalid_argument("Buffer Mapper is null");

        // bridge ImagePtr and hvaBuf
        hva::hvaVideoFrameWithROIBuf_t::Ptr buffer = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(input->get(0));
        InferenceBackend::ImagePtr image = m_buffer_mapper->map(buffer);
        // HVA_INFO("131");
        for (const auto& meta : metas) {
            
            ApplyImageBoundaries(image, meta, inference_property.inference_region_type);

            // prepare the variable to save results: ImageInferenceInstance::InferenceResult
            auto result = MakeInferenceResult(inference_property, m_model, meta, image, input);
            result->region_count = metas.size();
            // HVA_INFO("img width: %s", image->width);
            // HVA_INFO("img height: %s", image->height);

            // TODO: check if hvaBuf need this?
            // // Because image is a shared pointer with custom deleter which performs buffer unmapping
            // // we need to manually reset it after we passed it to the last InferenceResult
            // // Otherwise it may try to unmap buffer which is already pushed to downstream
            // // if completion callback is called before we exit this scope
            // if (++i == metas.size())
            //     image.reset();

            // support preprocess parameters, like: resize / crop etc.
            std::map<std::string, InferenceBackend::InputLayerDesc::Ptr> input_preprocessors;
            if (!m_model.input_processor_info.empty()) {
                input_preprocessors = GetInputPreprocessors(m_model.inference, m_model.input_processor_info, meta);
            }
            
            m_model.inference->SubmitImage(std::move(result), input_preprocessors);
            status = InferenceStatus::INFERENCE_EXECUTED;
        }
        
    } catch (const std::exception &e) {
        HVA_ERROR("Failed to submit images to inference, error: %s", e.what());
    }
    catch (...) {
        HVA_ERROR("Failed to submit images to inference");
    }
    return status;
}

void ImageInferenceInstance::CreateModel(InferenceProperty& inference_property) {

    // 
    // start to create model instance
    // 
    // ImageInferenceInstance::Model model;

    // parse model_proc config file (if not empty)
    std::string model_proc_cfg(inference_property.model_proc_config);
    if (!model_proc_cfg.empty()) {
        HVA_DEBUG("Start to parse model_proc_cfg file.");
        if (!Utils::fileExists(model_proc_cfg))
            throw std::invalid_argument("Model post-process config file '" + model_proc_cfg + "' does not exist");
        
        // parse pre-process info from model_proc_cfg
        ModelProcProvider model_proc_provider;
        model_proc_provider.readJsonFile(model_proc_cfg);
        m_model.input_processor_info = model_proc_provider.parseInputPreproc();
        // // TODO: what to do with post-process?
        // model.output_processor_info = model_proc_provider.parseOutputPostproc();
        HVA_DEBUG("Parse model_proc_cfg file done.");
    }

    if (inference_property.batch_size == 0)
        inference_property.batch_size = GetOptimalBatchSize(inference_property.device);

    UpdateModelReshapeInfo(inference_property);
    InferenceConfig inference_config = CreateNestedInferenceConfig(inference_property);
    UpdateConfigWithLayerInfo(m_model.input_processor_info, inference_config);

    // // TODO: input memory type should be configurable
    // // how do we know the input_image_memory_type at runtime? Seems should not set here? 
    // MemoryType input_image_memory_type = MemoryType::SYSTEM;
    // m_memory_type = GetMemoryType(
    //     input_image_memory_type,
    //     static_cast<ImagePreprocessorType>(
    //         std::stoi(inference_config[InferenceBackend::KEY_BASE][InferenceBackend::KEY_PRE_PROCESSOR_TYPE])));
    std::string device = inference_property.device;
    if (device.find("GPU") != std::string::npos || device.find("NPU") != std::string::npos) {
#ifdef ENABLE_VAAPI
        m_memory_type = MemoryType::VAAPI;
#else
        throw std::runtime_error("GPU support is not enabled!");
#endif
    } else {
        m_memory_type = MemoryType::SYSTEM;
    }
    m_buffer_mapper = BufferMapperFactory::createMapper(m_memory_type);

    // TODO: set ContextPtr (va_display) according to m_memory_type
    hce::ai::inference::ContextPtr va_dpy = nullptr;
#ifdef ENABLE_VAAPI
    // hce::ai::inference::VAAPIContextPtr va_dpy = nullptr;
    if (m_memory_type == MemoryType::VAAPI) {
        va_dpy = std::make_shared<hce::ai::inference::VAAPIContext>(VADeviceManager::getInstance().getVADisplay(inference_property.device_id));
        // HVA_DEBUG("va devicd id %d , VADisplay addr %p", inference_property.device_id, va_dpy->va_display());
    }
#endif

    // TODO
    // create ImageInference instance
    if (!m_callback_func || !m_callback_func_error_handle) {
        throw std::invalid_argument("Callback function should be set before creating models");
    }
    auto image_inference = ImageInference::make_shared(
        m_memory_type, inference_config, m_allocator.get(), m_callback_func,
        m_callback_func_error_handle, std::move(va_dpy));
    // auto image_inference = ImageInference::make_shared(
    //     m_memory_type, inference_config, m_allocator.get(),
    //     std::bind(&ImageInferenceInstance::InferenceCompletionCallback, this,
    //               std::placeholders::_1, std::placeholders::_2),
    //     std::bind(&ImageInferenceInstance::PushFramesIfInferenceFailed, this,
    //               std::placeholders::_1),
    //     std::move(va_dpy));
    if (!image_inference)
        throw std::runtime_error("Failed to create image inference");
    m_model.inference = image_inference;
    m_model.name = image_inference->GetModelName();
    
    // return model;
}

void ImageInferenceInstance::FlushInference() {
    m_model.inference->Flush();
}

inline std::shared_ptr<Allocator> ImageInferenceInstance::CreateAllocator(const std::string allocator_name) {
    std::shared_ptr<Allocator> allocator;
    if (!allocator_name.empty()) {
        // allocator = std::make_shared<GstAllocatorWrapper>(allocator_name);
        // GVA_TRACE("GstAllocatorWrapper is created");
        // TODO: implement
        throw std::runtime_error("Creating allocator not implemented yet!");
    }
    return allocator;
}

unsigned int ImageInferenceInstance::GetOptimalBatchSize(std::string device) {
    unsigned int batch_size = 1;
    // if the device has the format GPU.x we assume that these are discrete graphics and choose larger batch
    if (std::string(device).find("GPU.") != std::string::npos)
        batch_size = 64;
    return batch_size;
}

void ImageInferenceInstance::UpdateModelReshapeInfo(InferenceProperty& inference_property) {

    // reshape_width > 0 OR reshape_height > 0 OR batch_size > 1 can all affect model reshape action
    try {
        if (inference_property.reshape_model_input)
            return;

        if (inference_property.reshape_width > 0 || inference_property.reshape_height > 0) {
            HVA_DEBUG("reshape_model_input switched to TRUE because reshape_width or reshape_height more than 0");
            inference_property.reshape_model_input = true;
            return;
        }

        if (inference_property.batch_size > 1) {
            HVA_DEBUG("reshape_model_input switched to TRUE because batch-size more than 1");
            inference_property.reshape_model_input = true;
            return;
        }
    } catch (const std::exception &e) {
        std::throw_with_nested(std::runtime_error("Failed to update model reshape"));
    }
}

InferenceConfig ImageInferenceInstance::CreateNestedInferenceConfig(InferenceProperty& inference_property) {

    InferenceConfig config;
    std::map<std::string, std::string> base;

    // __CONFIG_KEY(name) KEY_##name defined in `InferenceBackend`
    base[InferenceBackend::KEY_MODEL] = inference_property.model_path;
    base[InferenceBackend::KEY_NIREQ] = std::to_string(inference_property.nireq);
    if (!inference_property.device.empty()) {
        std::string device = inference_property.device;
        base[InferenceBackend::KEY_DEVICE] = device;
    }

    // flexible ie config with key-value schema
    // inference_property.inference_config: [CPU_THROUGHPUT_STREAMS=6,CPU_THREADS_NUM=6,CPU_BIND_THREAD=NUMA]
    std::map<std::string, std::string> inference;
    for (const auto& cfg : inference_property.inference_config) {
        size_t index = cfg.find("=");
        if (index != std::string::npos) {
            std::string key(cfg, 0, index);
            std::string val(cfg, index + 1, cfg.size());
            inference[key] = val;
        }
        else {
            HVA_WARNING("IE config received invalid value: %s, ignore it!", cfg.c_str());
        }
    }

    // inference_property.device_extensions is "device1=extension1,device2=extension2"-like string
    base[InferenceBackend::KEY_DEVICE_EXTENSIONS] = inference_property.device_extensions;

    ImagePreprocessorType preprocType = ImagePreprocessorTypeFromString(inference_property.pre_proc_type);
    if (preprocType == ImagePreprocessorType::VAAPI_SURFACE_SHARING) {
        // gpu decode -> gpu inference
        base[InferenceBackend::KEY_IMAGE_FORMAT] = "NV12";
    } else if (preprocType == ImagePreprocessorType::IE){
        // cpu decode -> cpu inference
        base[InferenceBackend::KEY_IMAGE_FORMAT] = "BGR";
    }else if (preprocType == ImagePreprocessorType::OPENCV){
        base[InferenceBackend::KEY_IMAGE_FORMAT] = "BGR";
    }
    base[InferenceBackend::KEY_PRE_PROCESSOR_TYPE] = std::to_string(static_cast<int>(preprocType));
    std::map<std::string, std::string> pre_proc_config;
    for (const auto& cfg : inference_property.pre_proc_config) {
        size_t index = cfg.find("=");
        if (index != std::string::npos) {
            std::string key(cfg, 0, index);
            std::string val(cfg, index + 1, cfg.size());
            pre_proc_config[key] = val;
            HVA_INFO("pre_proc_config[%s] = %s", key.c_str(), val.c_str());
        }
        else {
            HVA_WARNING("IE config received invalid value: %s, ignore it!", cfg.c_str());
        }
    }
    config[InferenceBackend::KEY_PRE_PROCESSOR] = pre_proc_config;

    auto scale_factor_it = pre_proc_config.find(KEY_SCALE_FACTOR);
    std::string scale_factor_str = scale_factor_it == pre_proc_config.end() ? std::to_string(1.0) : scale_factor_it->second;
    base[InferenceBackend::KEY_SCALE_FACTOR] = scale_factor_str;

    base[InferenceBackend::KEY_BATCH_SIZE] = std::to_string(inference_property.batch_size);
    base[InferenceBackend::KEY_RESHAPE] = std::to_string(inference_property.reshape_model_input);
    HVA_INFO("inference_property.reshape_model_input: %d", inference_property.reshape_model_input);
    HVA_INFO("inference_property.reshape_width: %d", inference_property.reshape_width);
    HVA_INFO("inference_property.reshape_height: %d", inference_property.reshape_height);
    HVA_INFO("inference_property.batch_size: %d", inference_property.batch_size);
    HVA_INFO("inference_property.image_width: %d", inference_property.image_width);
    HVA_INFO("inference_property.image_height: %d", inference_property.image_height);
    if (inference_property.reshape_model_input) {
        if ((inference_property.reshape_width) || (inference_property.reshape_height) || (inference_property.batch_size > 1)) {
            base[InferenceBackend::KEY_RESHAPE_WIDTH] = std::to_string(inference_property.reshape_width);
            base[InferenceBackend::KEY_RESHAPE_HEIGHT] = std::to_string(inference_property.reshape_height);
        } else {
            // TODO get model input
            throw std::runtime_error("Not implemented yet.Get model input shape from IR");
        }
    }
    base[InferenceBackend::KEY_IMAGE_WIDTH] = std::to_string(inference_property.image_width);
    base[InferenceBackend::KEY_IMAGE_HEIGHT] = std::to_string(inference_property.image_height);
    HVA_INFO("base[InferenceBackend::KEY_RESHAPE_WIDTH] %s",base[InferenceBackend::KEY_RESHAPE_WIDTH].c_str());
    HVA_INFO("base[InferenceBackend::KEY_RESHAPE_HEIGHT] %s",base[InferenceBackend::KEY_RESHAPE_HEIGHT].c_str());
    HVA_INFO("base[InferenceBackend::KEY_IMAGE_WIDTH] %s",base[InferenceBackend::KEY_IMAGE_WIDTH].c_str());
    HVA_INFO("base[InferenceBackend::KEY_IMAGE_HEIGHT] %s",base[InferenceBackend::KEY_IMAGE_HEIGHT].c_str());
    config[InferenceBackend::KEY_BASE] = base;
    config[InferenceBackend::KEY_INFERENCE] = inference;
    return config;
}

ImagePreprocessorType ImageInferenceInstance::ImagePreprocessorTypeFromString(const std::string &image_preprocessor_name) {
    constexpr std::pair<const char *, ImagePreprocessorType> preprocessor_types[]{
        {"", ImagePreprocessorType::AUTO},
        {"ie", ImagePreprocessorType::IE},
        {"vaapi", ImagePreprocessorType::VAAPI_SYSTEM},
        {"vaapi-surface-sharing", ImagePreprocessorType::VAAPI_SURFACE_SHARING},
        {"opencv", ImagePreprocessorType::OPENCV}};

    for (auto &elem : preprocessor_types) {
        if (image_preprocessor_name == elem.first)
            return elem.second;
    }

    throw std::runtime_error("Invalid pre-process-backend property value provided: " + image_preprocessor_name +
                             ". Check element's description for supported property values.");
}

void ImageInferenceInstance::UpdateConfigWithLayerInfo(
    const std::vector<ModelInputInfo::Ptr>& model_input_processor_info,
    InferenceConfig& config) {

    std::map<std::string, std::string> input_layer_precision;
    std::map<std::string, std::string> input_layer_layout;
    std::map<std::string, std::string> input_format;
    for (const ModelInputInfo::Ptr& preproc :
        model_input_processor_info) {
        if (!preproc->layout.empty())
            input_layer_layout[preproc->layer_name] = preproc->layout;
        if (!preproc->precision.empty())
            input_layer_precision[preproc->layer_name] = preproc->precision;
        if (!preproc->format.empty())
            input_format[preproc->layer_name] = preproc->format;
    }

    config[InferenceBackend::KEY_INPUT_LAYER_PRECISION] = input_layer_precision;
    config[InferenceBackend::KEY_INPUT_LAYER_LAYOUT] = input_layer_layout;
    config[InferenceBackend::KEY_FORMAT] = input_format;
}

void ImageInferenceInstance::ApplyImageBoundaries(std::shared_ptr<InferenceBackend::Image>& image,
                            const VideoRegionOfInterestMeta& meta,
                            InferenceRegionType inference_region) {

    if (inference_region == FULL_FRAME) {
        image->rect = InferenceBackend::Rectangle<uint32_t>(0, 0, meta.width, meta.height);
        return;
    }

    // inference_region == ROI_LIST
    const int image_width = (int)image->width;
    const int image_height = (int)image->height;
    image->rect.x = std::min(meta.x, image_width);
    image->rect.y = std::min(meta.y, image_height);
    image->rect.width = ((meta.width + meta.x) > image_width) ? image_width - image->rect.x : meta.width;
    image->rect.height = ((meta.height, meta.y) > image_height) ? image_height - image->rect.y : meta.height;
}


std::shared_ptr<ImageInferenceInstance::InferenceResult>
ImageInferenceInstance::MakeInferenceResult(const InferenceProperty& inference_property, Model &model, 
                                       const VideoRegionOfInterestMeta& meta,
                                       std::shared_ptr<InferenceBackend::Image> &image,
                                       hva::hvaBlob_t::Ptr input) {
    auto result = std::make_shared<InferenceResult>();
    /* expect that std::make_shared must throw instead of returning nullptr */
    assert(result.get() != nullptr && "Expected a valid InferenceResult");

    result->inference_frame = std::make_shared<InferenceFrame>();
    /* expect that std::make_shared must throw instead of returning nullptr */
    assert(result->inference_frame.get() != nullptr && "Expected a valid InferenceFrame");

    result->inference_frame->roi = meta;

    result->model = &model;
    result->image = image;
    result->input = input;
    return result;
}


std::map<std::string, InputLayerDesc::Ptr>
    ImageInferenceInstance::GetInputPreprocessors(const std::shared_ptr<InferenceBackend::ImageInference> &inference,
                          const std::vector<ModelInputInfo::Ptr> &model_input_processor_info,const VideoRegionOfInterestMeta &roi) {
    std::map<std::string, InferenceBackend::InputLayerDesc::Ptr> preprocessors;
    for (const ModelInputInfo::Ptr &preproc : model_input_processor_info) {
        preprocessors[preproc->format] = std::make_shared<InputLayerDesc>(InputLayerDesc());
        preprocessors[preproc->format]->name = preproc->layer_name;
        GstVideoRegionOfInterestMeta* gstMeta = ConvertToGstMeta(roi);
        preprocessors[preproc->format]->preprocessor =
            getInputPreprocFunctrByLayerType(preproc->format, inference, preproc->params, gstMeta);

        // define transform function to directly process InferenceBackend::InputBlob::Ptr
        // preprocessors[preproc->format]->preprocessor = nullptr;

        // support resize / crop etc. via model_proc json fields (only for format: image)
        preprocessors[preproc->format]->input_image_preroc_params =
            (preproc->format == "image") ? PreProcParamsParser(preproc->params).parse() : nullptr;
    }
    return preprocessors;
}

// MemoryType ImageInferenceInstance::GetMemoryType(MemoryType input_image_memory_type, ImagePreprocessorType image_preprocessor_type) {
//     MemoryType type = MemoryType::ANY;
//     switch (input_image_memory_type) {
//         case MemoryType::SYSTEM: {
//             switch (image_preprocessor_type) {
//                 case ImagePreprocessorType::OPENCV:
//                 case ImagePreprocessorType::IE:
//                     type = MemoryType::SYSTEM;
//                     break;
//                 default:
//                     throw std::invalid_argument("For system memory only supports ie, opencv image preprocessors");
//             }
//             break;
//         }
//         case MemoryType::VAAPI:
//         case MemoryType::DMA_BUFFER: {
//             switch (image_preprocessor_type) {
//                 case ImagePreprocessorType::OPENCV:
//                 case ImagePreprocessorType::IE:
//                     type = MemoryType::SYSTEM;
//                     break;
//                 case ImagePreprocessorType::VAAPI_SURFACE_SHARING:
//                 case ImagePreprocessorType::VAAPI_SYSTEM:
//                     type = input_image_memory_type;
//                     break;
//                 default:
//                     throw std::invalid_argument("Invalid image preprocessor type");
//             }
//             break;
//         }
//         default:
//             break;
//     }
//     return type;
// }

} // namespace inference

} // namespace ai

} // namespace hce