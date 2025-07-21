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

#include "inference_nodes/ObjectQualityNode.hpp"

namespace hce{

namespace ai{

namespace inference{

ObjectQualityNode::ObjectQualityNode(std::size_t totalThreadNum)
    : baseImageInferenceNode(totalThreadNum) {

    // inference type
    m_inferenceProperties.inference_region_type = InferenceRegionType::ROI_LIST;
}

ObjectQualityNode::~ObjectQualityNode() {}

/**
* @brief Parse params, called by hva framework right after node instantiate.
* @param config Configure string required by this node.
*/
hva::hvaStatus_t ObjectQualityNode::configureByString(const std::string& config) {

    if(config.empty()){
        return hva::hvaFailure;
    }

    if(!m_configParser.parse(config)){
        HVA_ERROR("%s Illegal parse string!", nodeClassName().c_str());
        return hva::hvaFailure;
    }
    
    int quality_mode = 0;
    m_configParser.getVal<int>("QualityMode", quality_mode);

    if (quality_mode == QualityPredictor::QualityModeType_e::QUALITY_MODE_QAMODEL) {
        
        // inference type
        m_inferenceProperties.inference_type = InferenceType::HVA_REGRESSION_TYPE;
        
        // inherit from base inference node
        hva::hvaStatus_t sts = baseImageInferenceNode::configureByString(config);
        if (hva::hvaSuccess != sts) {
            return sts;
        }
        m_qualityPredictor = nullptr;
    }
    else if (quality_mode == QualityPredictor::QualityModeType_e::QUALITY_MODE_RANDOM ||
             quality_mode == QualityPredictor::QualityModeType_e::QUALITY_MODE_BLUR) {

        m_inferenceProperties.inference_type = InferenceType::HVA_NONE_TYPE;
        m_qualityPredictor = std::make_shared<QualityPredictor>();
            
        // image size for calculating laplacian variance, default as 320.
        int imageSize = 320;
        m_configParser.getVal<int>("ImageSize", imageSize);
        m_qualityPredictor->init(quality_mode, imageSize);
    }
    else {
        HVA_ERROR("%s Illegal quality mode: %u", nodeClassName().c_str(), quality_mode);
        return hva::hvaFailure;
    }

    // after all configures being parsed, this node should be trainsitted to `configured`
    transitStateTo(hva::hvaState_t::configured);
    return hva::hvaSuccess;
}    

/**
* @brief prepare and intialize this hvaNode_t instance. 
*           > quality_mode: QUALITY_MODE_RANDOM | QUALITY_MODE_BLUR, init m_qualityPredictor
*           > quality_mode: QUALITY_MODE_QAMODEL, create Postprocessor
* 
* @param void
* @return hvaSuccess if success
*/
hva::hvaStatus_t ObjectQualityNode::prepare() {

    if (m_qualityPredictor != nullptr) {
        // do not use DL inference, init m_qualityPredictor (opencv)
        return m_qualityPredictor->prepare();
    }
    else {
        // use DL inference
        hva::hvaStatus_t sts = baseImageInferenceNode::prepare();

        if (hva::hvaSuccess != sts) {
            return sts;
        }
        // TODO
        return hva::hvaSuccess;
    }
}

/**
 * @brief Constructs and returns a node worker instance:
 * ObjectQualityNodeWorker.
 * @param void
 */
std::shared_ptr<hva::hvaNodeWorker_t> ObjectQualityNode::createNodeWorker() 
    const {
    return std::shared_ptr<hva::hvaNodeWorker_t>(new ObjectQualityNodeWorker(
        (hva::hvaNode_t*)this, m_inferenceProperties, m_inferenceInstance));
}


ObjectQualityNodeWorker::ObjectQualityNodeWorker(
    hva::hvaNode_t* parentNode, InferenceProperty inferenceProperty,
    ImageInferenceInstance::Ptr instance) 
    : baseImageInferenceNodeWorker(parentNode, inferenceProperty, instance) {
        m_nodeName = ((ObjectQualityNode*)getParentPtr())->nodeClassName();
        // m_postProcessors = ((ObjectQualityNode*)getParentPtr())->getPostProcessors();
        m_qualityPredictor = ((ObjectQualityNode*)getParentPtr())->getQualityPredictor();
}

ObjectQualityNodeWorker::~ObjectQualityNodeWorker() {}

/**
 * @brief Called by hva framework for each video frame, Run inference and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void ObjectQualityNodeWorker::process(std::size_t batchIdx) {
    
    if (m_qualityPredictor == nullptr) {
        // QUALITY_MODE_QAMODEL

        // 
        // run inference
        // 
        baseImageInferenceNodeWorker::process(batchIdx);
    }
    else {
        // QUALITY_MODE_RANDOM || QUALITY_MODE_BLUR (opencv)
        std::vector<std::vector<hva::hvaBlob_t::Ptr>> collectedInputs = getInput(batchIdx);

        // input blob is empty
        if (collectedInputs.size() == 0) {
            return;
        }

        try {
            // TODO how to support multi-port case?
            
            // inputs come from identical port of hvaNode
            auto inputs = collectedInputs[0];
            HVA_DEBUG("%s start to submit inference with %d inputs", m_nodeName.c_str(), inputs.size());

            for (auto& curInput : inputs) {
                
                HVA_DEBUG("%s %d on frameId %d and streamid %u", m_nodeName.c_str(), batchIdx, curInput->frameId, curInput->streamId);
                
                if (!validateInput(curInput)) {
                    continue;
                }

                hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(curInput->get(0));
                HceDatabaseMeta inputMeta;
                ptrFrameBuf->getMeta(inputMeta);

                int input_height = ptrFrameBuf->height;
                int input_width = ptrFrameBuf->width;

                const uint8_t* pBuffer;
                cv::Mat decodedImage;

                if (inputMeta.bufType == HceDataMetaBufType::BUFTYPE_UINT8) {
                    // read image data from buffer
                    pBuffer = ptrFrameBuf->get<uint8_t*>();
                    if(pBuffer == NULL){
                        HVA_DEBUG("%s receiving an empty buffer on frameid %u and streamid %u, skipping", 
                                    m_nodeName.c_str(), curInput->frameId, curInput->streamId);
                        ptrFrameBuf->rois.clear();
                        sendOutput(curInput, 0, std::chrono::milliseconds(0));
                        continue;
                    }
                    decodedImage = cv::Mat(input_height, input_width, CV_8UC3, (uint8_t*)pBuffer);
                } else if (inputMeta.bufType == HceDataMetaBufType::BUFTYPE_MFX_FRAME) {
#ifdef ENABLE_VAAPI
                    HVA_WARNING("Buffer type of mfxFrame is received, will do mapping. This may slow down pipeline performance");
                    std::string dataStr;
                    mfxFrameSurface1* surfPtr = ptrFrameBuf->get<mfxFrameSurface1*>();
                    if (surfPtr == NULL) {
                        HVA_DEBUG("%s receiving an empty buffer on frameid %u and streamid %u, skipping", 
                                    m_nodeName.c_str(), curInput->frameId, curInput->streamId);
                        ptrFrameBuf->rois.clear();
                        sendOutput(curInput, 0, std::chrono::milliseconds(0));
                        continue;
                    }
                    surfPtr->FrameInterface->AddRef(surfPtr);
                    WriteRawFrame_InternalMem(surfPtr, dataStr);
                    pBuffer = (uint8_t*)dataStr.c_str();
                    input_height *= 1.5;
                    cv::Mat tempMat(input_height, input_width, CV_8UC1, (uint8_t*)pBuffer);
                    cv::cvtColor(tempMat, decodedImage, cv::COLOR_YUV2BGR_NV12);
#else
                    HVA_ERROR("Buffer type of mfxFrame is received but GPU support is not enabled");
                    sendOutput(curInput, 0, std::chrono::milliseconds(0));
                    continue;
#endif
                } else {
                    HVA_ERROR("Unsupported buffer type");
                    sendOutput(curInput, 0, std::chrono::milliseconds(0));
                    continue;
                }

                // traverse each roi
                for (size_t roi_index = 0; roi_index < ptrFrameBuf->rois.size(); roi_index++)
                {   
                    const size_t x = static_cast<size_t>(ptrFrameBuf->rois[roi_index].x);
                    const size_t y = static_cast<size_t>(ptrFrameBuf->rois[roi_index].y);
                    const size_t w = static_cast<size_t>(ptrFrameBuf->rois[roi_index].width);
                    const size_t h = static_cast<size_t>(ptrFrameBuf->rois[roi_index].height);

                    // crop roiImage from input, OpenCV Mat
                    cv::Rect2i cropRoi({x, y, w, h});
                    const cv::Mat roiImage = decodedImage(cropRoi);

                    float qualityScore = m_qualityPredictor->predict(roiImage);
                    inputMeta.qualityResult.emplace(std::make_pair(roi_index, qualityScore));
                }

                // update meta for this input
                ptrFrameBuf->setMeta(inputMeta);
                
                // sendOutput
                HVA_DEBUG("%s sending blob with frameid %u and streamid %u", m_nodeName.c_str(), curInput->frameId, curInput->streamId);
                sendOutput(curInput, 0, std::chrono::milliseconds(0));
                HVA_DEBUG("%s completed sent blob with frameid %u and streamid %u", m_nodeName.c_str(), curInput->frameId, curInput->streamId);

            }

        } catch (const std::exception &e) {
            HVA_ERROR("%s failed on frame processing, error: %s", m_nodeName.c_str(), e.what());
        }
        catch (...) {
            HVA_ERROR("%s failed on frame processing", m_nodeName.c_str());
        }
    }
}

/**
 * @brief would be called at the end of each process() to send outputs to the
 * downstream nodes.
 * @param blobs each InferenceBackend::OutputBlob::Ptr contains a batched output blob buffer
 * @param frames equals to batchsize
 * @return void
 */
void ObjectQualityNodeWorker::processOutput(
    std::map<std::string, InferenceBackend::OutputBlob::Ptr> blobs,
    std::vector<std::shared_ptr<InferenceBackend::ImageInference::IFrameBase>> frames) {

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
        HVA_DEBUG("%s processed output on frameid %u and streamid %u", m_nodeName.c_str(), curInput->frameId, curInput->streamId);
        m_inputBlobs.put(curInput);
        HceDatabaseMeta inputMeta;
        curInput->get(0)->getMeta(inputMeta);

        std::shared_ptr<InferenceFrame> inference_roi = inference_result->inference_frame;
        inference_roi->image_transform_info = inference_result->GetImageTransformationParams();

        inference_result->image.reset(); // deleter will to not make buffer_unref, see 'SubmitImages' method

        // 
        // post-process
        // 
		hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(curInput->get(0));
        HVA_ASSERT(ptrFrameBuf);

        if (blobs.size() > 1) {
            HVA_ERROR("%s do not support for multiple output layer!", m_nodeName.c_str());
            HVA_ASSERT(false);
        }

        for (const auto& output : blobs) {
            std::string outputLayerName = output.first;
            InferenceBackend::OutputBlob::Ptr outputBlob = output.second;

            // dims: [N, ...], the first axis stands for batch
            auto dims = outputBlob->GetDims();
            size_t dataLength = outputBlob->GetSize() / dims[0];
            float* blobData = (float*)outputBlob->GetData() + batchIdx * dataLength;
            
            // fetch blob data from output layer
            float score = blobData[0];
            inputMeta.qualityResult.emplace(std::make_pair(inference_roi->roi.roi_id, score));

            HVA_DEBUG("quality score: %f", score);
        }

        // update meta for this input
        ptrFrameBuf->setMeta(inputMeta);

        // 
        // update output frames
        // 
        if (m_inputBlobs.isCompletedInference(curInput, inference_result->region_count)) {

            // sendOutput
            HVA_DEBUG("%s sending blob with frameid %u and streamid %u", m_nodeName.c_str(), curInput->frameId, curInput->streamId);
            sendOutput(curInput, 0, std::chrono::milliseconds(0));
            HVA_DEBUG("%s completed sent blob with frameid %u and streamid %u", m_nodeName.c_str(), curInput->frameId, curInput->streamId);

            // release `depleting` status in hva pipeline
            HVA_DEBUG("%s release depleting on frameid %u and streamid %u", m_nodeName.c_str(), curInput->frameId, curInput->streamId);
            getParentPtr()->releaseDepleting();

            // remove this input from records
            m_inputBlobs.erase(curInput);
        }
    }
}


#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(ObjectQualityNode, ObjectQualityNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

} // namespace inference

} // namespace ai

} // namespace hce
