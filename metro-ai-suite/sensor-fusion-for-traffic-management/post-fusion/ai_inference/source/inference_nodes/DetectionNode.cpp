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

#include "inference_nodes/DetectionNode.hpp"

namespace hce {

namespace ai {

namespace inference {

DetectionNode::DetectionNode(std::size_t totalThreadNum) : baseImageInferenceNode(totalThreadNum)
{
    // inference type
    m_inferenceProperties.inference_type = InferenceType::HVA_DETECTION_TYPE;
    m_inferenceProperties.inference_region_type = InferenceRegionType::FULL_FRAME;
}

DetectionNode::~DetectionNode() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 */
hva::hvaStatus_t DetectionNode::configureByString(const std::string &config)
{
    hva::hvaStatus_t sts = baseImageInferenceNode::configureByString(config);

    if (hva::hvaSuccess != sts) {
        return sts;
    }

    if (m_inferenceProperties.model_proc_config.empty()) {
        HVA_ERROR("%s ModelProcConfPath must be configured!", nodeClassName().c_str());
        return hva::hvaStatus_t::hvaFailure;
    }

    m_threshold = 0.6;
    m_configParser.getVal<float>("Threshold", m_threshold);

    m_maxROI = 0;
    m_configParser.getVal<int>("MaxROI", m_maxROI);

    // filterLabels record labels need to be kept.
    // default as empty to keep all proposals
    m_configParser.getVal<std::vector<std::string>>("FilterLabels", m_filterLabels);

    // after all configures being parsed, this node should be trainsitted to `configured`
    transitStateTo(hva::hvaState_t::configured);
    return sts;
}

/**
 * @brief prepare and intialize this hvaNode_t instance. Create Postprocessor
 *
 * @param void
 * @return hvaSuccess if success
 */
hva::hvaStatus_t DetectionNode::prepare()
{
    hva::hvaStatus_t sts = baseImageInferenceNode::prepare();

    if (hva::hvaSuccess != sts) {
        return sts;
    }
    // parse post_procs and labels from model_proc file
    try {
        std::string modelProcConfPath(m_inferenceProperties.model_proc_config);
        DetectionModelProcParser proc_parser(modelProcConfPath);
        if (!proc_parser.parse()) {
            HVA_ERROR("Failed to parse post process configuration json file: %s", modelProcConfPath.c_str());
            return hva::hvaStatus_t::hvaFailure;
        }

        auto postprocParams = proc_parser.getModelProcParams();

        // init post processors for Detection model, detection models use the unified converter: "HVADet"
        m_postProcessor = DetectionPostProcessor::Ptr(new DetectionPostProcessor());
        m_postProcessor->init(postprocParams, m_filterLabels, m_threshold, m_maxROI);

        std::string modelProcLibPath(m_inferenceProperties.model_proc_lib);
        if (!modelProcLibPath.empty()) {
            // RTLD_NOW: If this value is specified, all undefined symbols in the library are resolved before dlopen() returns.
            //           If this cannot be done, an error is returned.
            // RTLD_GLOBAL: The symbols defined by this library will be made available for symbol resolution of subsequently loaded libraries.
            m_postProcessorCustomHandle = dlopen(modelProcLibPath.c_str(), RTLD_NOW | RTLD_GLOBAL);
            if (!m_postProcessorCustomHandle) {
                HVA_ERROR("%s failed to load custom post process library, error: %s", nodeClassName().c_str(), dlerror());
                return hva::hvaFailure;
            }
        }
        else {
            // do not load custom library
            m_postProcessorCustomHandle = nullptr;
        }
    }
    catch (const std::exception &e) {
        HVA_ERROR("%s failed to create post processor, error: %s!", nodeClassName().c_str(), e.what());
        return hva::hvaStatus_t::hvaFailure;
    }
    catch (...) {
        HVA_ERROR("%s failed to create post processor!", nodeClassName().c_str());
        return hva::hvaStatus_t::hvaFailure;
    }

    if (!m_postProcessor) {
        HVA_ERROR("%s failed to create post processor!", nodeClassName().c_str());
        return hva::hvaStatus_t::hvaFailure;
    }
    HVA_DEBUG("%s created post processor", nodeClassName().c_str());
    return hva::hvaSuccess;
}

/**
 * @brief Constructs and returns a node worker instance:
 * DetectionNodeWorker.
 * @param void
 */
std::shared_ptr<hva::hvaNodeWorker_t> DetectionNode::createNodeWorker() const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new DetectionNodeWorker((hva::hvaNode_t *)this, m_inferenceProperties, m_inferenceInstance));
}


DetectionNodeWorker::DetectionNodeWorker(hva::hvaNode_t *parentNode, InferenceProperty inferenceProperty, ImageInferenceInstance::Ptr instance)
    : baseImageInferenceNodeWorker(parentNode, inferenceProperty, instance)
{
    m_nodeName = ((DetectionNode *)getParentPtr())->nodeClassName();
    m_postProcessor = ((DetectionNode *)getParentPtr())->getPostProcessors();
    m_postProcessorCustomHandle = ((DetectionNode *)getParentPtr())->getPostProcessorCustomHandle();
}

DetectionNodeWorker::~DetectionNodeWorker() {}

/**
 * @brief erase detected rois outside filter region
 * @param filter filter region
 * @param rois detected rois
 * @param filter_thresh should be different with NMS's iou threshold
 */
void DetectionNodeWorker::filterROI(const hva::hvaROI_t &filter, std::vector<hva::hvaROI_t> &rois, float filter_thresh)
{
    if (filter.x == 0 && filter.y == 0 && filter.width == 0 && filter.height == 0) {
        // skip filtering if filter is all 0
        return;
    }

    if (filter_thresh == 0) {
        // skip if threshold is 0
        return;
    }

    float areaBaseline = filter.height * filter.width;  // rect.height * rect.width;

    // traver all rois and erase those outside filter region
    for (auto iter = rois.begin(); iter != rois.end();) {
        bool isOverlapped = false;
        float area = iter->height * iter->width;  // rectPrev.height * rectPrev.width;

        float x1 = std::max(filter.x, iter->x);
        float y1 = std::max(filter.y, iter->y);
        float x2 = std::min(filter.x + filter.width, iter->x + iter->width);
        float y2 = std::min(filter.y + filter.height, iter->y + iter->height);

        float areaIntersect = std::max(0.0f, x2 - x1) * std::max(0.0f, y2 - y1);

        if (area + areaBaseline - areaIntersect > 0.0f) {
            float iou1 = areaIntersect / areaBaseline;  // not a standard iou!
            float iou2 = areaIntersect / area;          // not a standard iou!
            isOverlapped = (iou1 >= filter_thresh) || (iou2 >= filter_thresh);
        }
        else {
            isOverlapped = true;
        }

        // inplace erasing
        if (!isOverlapped) {
            iter = rois.erase(iter);
            HVA_DEBUG("Erased an roi from roi filtering");
        }
        else {
            ++iter;
        }
    }
}

/**
 * @brief run post processing on model outputs
 * @param blobData <layer_name, inference_blob_data>
 * @param blobLength <layer_name, blob_length>
 * @param hvaROIs save the parsed roi results
 * @param heightInput original image height
 * @param widthInput original image width
 * @return boolean
 */
bool DetectionNodeWorker::runPostproc(std::map<std::string, float *> blobData,
                                      std::map<std::string, size_t> blobLength,
                                      std::vector<hva::hvaROI_t> &hvaROIs,
                                      size_t heightInput,
                                      size_t widthInput,
                                      size_t targetBatchId)
{
    std::string json_results;
    std::string pp_function = m_postProcessor->getPPFunctioName();

    if (pp_function == "HVA_det_postproc") {
        // in-scope post processing function
        try {
            json_results = m_postProcessor->postproc(blobData, blobLength, targetBatchId);
        }
        catch (std::exception &e) {
            HVA_ERROR("%s failed to run post processing, error: %s!", m_nodeName.c_str(), e.what());
            return false;
        }
        catch (...) {
            HVA_ERROR("%s failed to run post processing!", m_nodeName.c_str());
            return false;
        }
    }
    else {
        /* load custom library and run corresponding function() to do the post-processing */
        try {
            // function named as {pp_function} should be defined in custom library
            load_customPostProcessor customPostProc = (load_customPostProcessor)dlsym(m_postProcessorCustomHandle, pp_function.c_str());
            char *pPerror = NULL;
            if ((pPerror = dlerror()) != NULL) {
                HVA_ERROR("%s failed to load custom post processor library, error: %s!", m_nodeName.c_str(), pPerror);
                return false;
            }
            json_results = customPostProc(blobData, blobLength, m_postProcessor->getConfThreshold(), targetBatchId);
        }
        catch (std::exception &e) {
            HVA_ERROR("Not implemented for function: %s yet!", pp_function.c_str());
            return false;
        }
    }

    /**
     * @brief Format json_results to std::vector<DetectedObject_t>
     *
     * json_results schema:
     * {
            "format": [
                {
                    "bbox": [
                        float,
                        float,
                        float,
                        float
                    ],
                    "confidence": float,
                    "label_id": int
                },
                ...
            ]
        }
    */
    // all the parsed objects bounding box should be normalized in [0.0, 1.0]
    std::vector<DetectedObject_t> vecObjects;
    if (!DetectionPostProcessor::parseHVADetFormatResult(json_results, vecObjects)) {
        HVA_ERROR("Failed to parse detection json results: %s", json_results.c_str());
        return false;
    }

    // write all results to `hvaROIs`
    hvaROIs.clear();

    //
    // Clip bboxes and rescale with image size
    //
    for (auto &object : vecObjects) {
        // get real coordinates according to image size
        object.x = object.x * widthInput;
        object.w = object.w * widthInput;
        object.y = object.y * heightInput;
        object.h = object.h * heightInput;

        // filter low confidence predictions
        if (object.confidence < m_postProcessor->getConfThreshold()) {
            continue;
        }

        std::string predictLabel = m_postProcessor->getLabels()->label_name(object.class_id);
        if (!m_postProcessor->isFilterLabel(predictLabel)) {
            HVA_DEBUG("object detected: x is %f, y is %f, w is %f, h is %f, label: %s, but filtered it out.", object.x, object.y, object.w, object.h,
                      predictLabel.c_str());
            continue;
        }
        hva::hvaROI_t roi;
        roi.x = object.x + 0.5f;
        roi.y = object.y + 0.5f;
        roi.height = object.h + 0.5f;
        roi.width = object.w + 0.5f;

        if (roi.x >= widthInput) {
            roi.x = widthInput - 1;
        }

        if (roi.y >= heightInput) {
            roi.y = heightInput - 1;
        }

        if (roi.width < 1) {
            roi.width = 1;
        }

        if (roi.height < 1) {
            roi.height = 1;
        }

        if (roi.x + roi.width > widthInput) {
            roi.width = widthInput - roi.x;
        }

        if (roi.y + roi.height > heightInput) {
            roi.height = heightInput - roi.y;
        }

        roi.confidenceDetection = object.confidence;
        roi.labelIdDetection = object.class_id;
        roi.labelDetection = predictLabel;
        hvaROIs.push_back(roi);

        HVA_DEBUG("object detected: x is %f, y is %f, w is %f, h is %f, label: %s, confidence: %f", object.x, object.y, object.w, object.h,
                  predictLabel.c_str(), object.confidence);
    }

    return true;
}

/**
 * @brief would be called at the end of each process() to send outputs to the
 * downstream nodes.
 * @return void
 */
void DetectionNodeWorker::processOutput(std::map<std::string, InferenceBackend::OutputBlob::Ptr> blobs,
                                        std::vector<std::shared_ptr<InferenceBackend::ImageInference::IFrameBase>> frames)
{
    HVA_DEBUG("%s processOutput", m_nodeName.c_str());
    if (frames.size() == 0) {
        HVA_ERROR("%s received none inference results!", m_nodeName.c_str());
        HVA_ASSERT(false);
    }
    size_t batchSize = frames.size();

    //
    // processing all outputs in async inference mode.
    //
    for (size_t batchIdx = 0; batchIdx < batchSize; batchIdx++) {
        auto inference_result = std::dynamic_pointer_cast<ImageInferenceInstance::InferenceResult>(frames[batchIdx]);
        /* InferenceResult is inherited from IFrameBase */
        assert(inference_result.get() != nullptr && "Expected a valid InferenceResult");

        hva::hvaBlob_t::Ptr curInput = inference_result->input;
        // std::shared_ptr<hva::timeStampInfo> inferenceOut = std::make_shared<hva::timeStampInfo>(curInput->frameId, "inferenceOut");
        // getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &inferenceOut);
        HVA_DEBUG("%s processed output on frameid %u and streamid %u", m_nodeName.c_str(), curInput->frameId, curInput->streamId);
        m_inputBlobs.put(curInput);

        std::shared_ptr<InferenceFrame> inference_roi = inference_result->inference_frame;
        inference_roi->image_transform_info = inference_result->GetImageTransformationParams();

        inference_result->image.reset();  // deleter will to not make buffer_unref, see 'SubmitImages' method

        //
        // post-process
        //
        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(curInput->get(0));
        HVA_ASSERT(ptrFrameBuf);
        HceDatabaseMeta inputMeta;
        ptrFrameBuf->getMeta(inputMeta);

        InferenceTimeStamp_t inferenceTimeMeta;
        if (ptrFrameBuf->getMeta(inferenceTimeMeta) == hva::hvaSuccess) {
            HVA_DEBUG("DetectionNode get inferenceTimeMeta from input buffer");
            std::chrono::time_point<std::chrono::high_resolution_clock> currentTime = std::chrono::high_resolution_clock::now();
            inferenceTimeMeta.endTime = currentTime;
            ptrFrameBuf->setMeta(inferenceTimeMeta);
        }


        // fetch blob data for current batch_index
        std::map<std::string, float *> blobData;
        std::map<std::string, size_t> blobLength;
        int batchid_index = m_postProcessor->getModelProcParams().model_output.detection_output.batchid_index;
        for (const auto &output : blobs) {
            std::string outputLayerName = output.first;
            InferenceBackend::OutputBlob::Ptr outputBlob = output.second;

            // dims: [N, ...], the first axis stands for batch
            auto dims = outputBlob->GetDims();
            size_t dataLength = outputBlob->GetSize() / dims[0];
            float *dataPtr;

            if (batchid_index >= 0) {
                // batchid_index may be defined in openvino op: `DetectionOutput`
                // use batchid_index to specify outputs for batch
                dataPtr = (float *)outputBlob->GetData();
            }
            else {
                dataPtr = (float *)outputBlob->GetData() + batchIdx * dataLength;
            }
            blobData.emplace(outputLayerName, dataPtr);
            blobLength.emplace(outputLayerName, dataLength);
        }

        int input_width = ptrFrameBuf->width;
        int input_height = ptrFrameBuf->height;
        std::vector<hva::hvaROI_t> vecObjects;
        if (!runPostproc(blobData, blobLength, vecObjects, input_height, input_width, batchIdx)) {
            HVA_WARNING("%s failed to run post process on model outputs!", m_nodeName.c_str());
        }

        // transform predicted objects according to the image_transform_info
        if (inference_roi->image_transform_info && inference_roi->image_transform_info->WasTransformation()) {
            for (auto &object : vecObjects) {
                // Note: The transformation info is respect to model input(i.e., input_before_transform_w, input_before_transform_h)!!
                float x = (float)object.x / input_width * inference_roi->image_transform_info->input_before_transform_w;
                float y = (float)object.y / input_height * inference_roi->image_transform_info->input_before_transform_h;
                float width = (float)object.width / input_width * inference_roi->image_transform_info->input_before_transform_w;
                float height = (float)object.height / input_height * inference_roi->image_transform_info->input_before_transform_h;
                /* take the paddings->crop->resize into account */
                if (inference_roi->image_transform_info->WasPadding()) {
                    x -= inference_roi->image_transform_info->padding_size_x;
                    y -= inference_roi->image_transform_info->padding_size_y;
                }
                if (inference_roi->image_transform_info->WasCrop()) {
                    x += inference_roi->image_transform_info->croped_border_size_x;
                    y += inference_roi->image_transform_info->croped_border_size_y;
                }
                if (inference_roi->image_transform_info->WasResize()) {
                    if (inference_roi->image_transform_info->resize_scale_x) {
                        x /= inference_roi->image_transform_info->resize_scale_x;
                        width /= inference_roi->image_transform_info->resize_scale_x;
                    }
                    if (inference_roi->image_transform_info->resize_scale_y) {
                        y /= inference_roi->image_transform_info->resize_scale_y;
                        height /= inference_roi->image_transform_info->resize_scale_y;
                    }
                }

                // clip
                x = (x < 0) ? 0 : (x >= input_width) ? (input_width - 1) : x;
                y = (y < 0) ? 0 : (y >= input_height) ? (input_height - 1) : y;
                width = ((x + width) > input_width) ? (input_width - x) : width;
                height = ((y + height) > input_height) ? (input_height - y) : height;

                object.x = (int)x;
                object.y = (int)y;
                object.width = (int)width;
                object.height = (int)height;
            }
        }

        if (vecObjects.size() != 0) {
            // rois received in detection node will be treated as filter region
            hva::hvaROI_t roiFiltered;
            if (!ptrFrameBuf->rois.empty()) {
                roiFiltered = ptrFrameBuf->rois[0];
                HVA_DEBUG("%s receives a buffer with filtering roi: [%d, %d, %d, %d]", m_nodeName.c_str(), roiFiltered.x, roiFiltered.y, roiFiltered.width,
                          roiFiltered.height);
                // clear the roi buffer as this will only contain the result roi after detection
                ptrFrameBuf->rois.clear();
            }

            // filtered rois outside filter region
            filterROI(roiFiltered, vecObjects);

            if (m_postProcessor->getMaxROI() == 0) {
                // no max, save all the buffers
                ptrFrameBuf->rois = vecObjects;
            }
            else {
                std::sort(vecObjects.begin(), vecObjects.end(),
                          [](const hva::hvaROI_t &a, const hva::hvaROI_t &b) { return a.confidenceDetection > b.confidenceDetection; });
                // if maxROI is set, keep rois with topK condifence
                int topk = std::min((int)vecObjects.size(), m_postProcessor->getMaxROI());
                for (int i = 0; i < topk; ++i) {
                    ptrFrameBuf->rois.push_back(vecObjects[i]);
                }
            }
        }
        else {
            HVA_DEBUG("Nothing detected on frameid %u and streamid %u", curInput->frameId, curInput->streamId);
            ptrFrameBuf->rois.clear();
        }

        // update meta for this input
        ptrFrameBuf->setMeta(inputMeta);

        //
        // update output frames
        //
        if (m_inputBlobs.isCompletedInference(curInput, inference_result->region_count)) {
            // getLatencyMonitor().stopRecording("inference");

            // sendOutput
            HVA_DEBUG("%s sending blob with frameid %u and streamid %u", m_nodeName.c_str(), curInput->frameId, curInput->streamId);
            std::shared_ptr<hva::timeStampInfo> detectionOut = std::make_shared<hva::timeStampInfo>(curInput->frameId, "detectionOut");
            getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &detectionOut);
            // getLatencyMonitor().stopRecording("inference");

            sendOutput(curInput, 0, std::chrono::milliseconds(0));
            HVA_DEBUG("%s completed sent blob with frameid %u and streamid %u", m_nodeName.c_str(), curInput->frameId, curInput->streamId);

            // if (curInput->frameId < 5) {
            //     std::shared_ptr<hva::timeStampInfo> detectionOut = std::make_shared<hva::timeStampInfo>(curInput->frameId, "detectionOut");
            //     getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &detectionOut);
            // }

            // release `depleting` status in hva pipeline
            HVA_DEBUG("%s release depleting on frameid %u and streamid %u", m_nodeName.c_str(), curInput->frameId, curInput->streamId);
            getParentPtr()->releaseDepleting();

            // remove this input from records
            m_inputBlobs.erase(curInput);
        }
    }
}


#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(DetectionNode, DetectionNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce
