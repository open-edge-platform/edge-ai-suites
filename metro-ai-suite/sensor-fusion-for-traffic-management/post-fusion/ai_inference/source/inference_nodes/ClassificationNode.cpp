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

#include "inference_nodes/ClassificationNode.hpp"

namespace hce{

namespace ai{

namespace inference{

ClassificationNode::ClassificationNode(std::size_t totalThreadNum)
    : baseImageInferenceNode(totalThreadNum) {

    // inference type
    m_inferenceProperties.inference_type = InferenceType::HVA_CLASSIFICATION_TYPE;
    m_inferenceProperties.inference_region_type = InferenceRegionType::ROI_LIST;
}

ClassificationNode::~ClassificationNode() {}

/**
* @brief Parse params, called by hva framework right after node instantiate.
* @param config Configure string required by this node.
*/
hva::hvaStatus_t ClassificationNode::configureByString(const std::string& config) {
    
    hva::hvaStatus_t sts = baseImageInferenceNode::configureByString(config);

    if (hva::hvaSuccess != sts) {
        return sts;
    }
    
    if (m_inferenceProperties.model_proc_config.empty()) {
        HVA_ERROR("%s ModelProcConfPath must be configured!", nodeClassName().c_str());
        return hva::hvaStatus_t::hvaFailure;
    }

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
hva::hvaStatus_t ClassificationNode::prepare() {
    
    hva::hvaStatus_t sts = baseImageInferenceNode::prepare();

    if (hva::hvaSuccess != sts) {
        return sts;
    }
    // parse post_procs and labels from model_proc file
    try {
        std::string modelProcConfPath(m_inferenceProperties.model_proc_config);
        ClassificationModelProcParser proc_parser(modelProcConfPath);
        if (!proc_parser.parse()) {
            HVA_ERROR("Failed to parse post process configuration json file: %s", modelProcConfPath.c_str());
            return hva::hvaStatus_t::hvaFailure;
        }
        // pair: <layer_name, model_param>
        auto postprocParams = proc_parser.getModelProcParams();
        
        // init post processors for Classification model
        for (auto& item : postprocParams) {
            auto postProcessor = ClassificationPostProcessor::Ptr(new ClassificationPostProcessor());
            postProcessor->init(item.second);
            m_postProcessors.emplace(item.first, postProcessor);
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
    
    if (m_postProcessors.size() == 0) {
        HVA_ERROR("%s failed to create post processor!", nodeClassName().c_str());
        return hva::hvaStatus_t::hvaFailure;
    }
    HVA_DEBUG("%s created post processor", nodeClassName().c_str());
    return hva::hvaSuccess;
}

/**
 * @brief Constructs and returns a node worker instance:
 * ClassificationNodeWorker.
 * @param void
 */
std::shared_ptr<hva::hvaNodeWorker_t> ClassificationNode::createNodeWorker() 
    const {
    return std::shared_ptr<hva::hvaNodeWorker_t>(new ClassificationNodeWorker(
        (hva::hvaNode_t*)this, m_inferenceProperties, m_inferenceInstance));
}


ClassificationNodeWorker::ClassificationNodeWorker(
    hva::hvaNode_t* parentNode, InferenceProperty inferenceProperty,
    ImageInferenceInstance::Ptr instance) 
    : baseImageInferenceNodeWorker(parentNode, inferenceProperty, instance) {
        m_nodeName = ((ClassificationNode*)getParentPtr())->nodeClassName();
        m_postProcessors = ((ClassificationNode*)getParentPtr())->getPostProcessors();
}

ClassificationNodeWorker::~ClassificationNodeWorker() {}

/**
 * @brief would be called at the end of each process() to send outputs to the
 * downstream nodes.
 * @param blobs each InferenceBackend::OutputBlob::Ptr contains a batched output blob buffer
 * @param frames equals to batchsize
 * @return void
 */
void ClassificationNodeWorker::processOutput(
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

        std::shared_ptr<InferenceFrame> inference_roi = inference_result->inference_frame;
        inference_roi->image_transform_info = inference_result->GetImageTransformationParams();

        inference_result->image.reset(); // deleter will to not make buffer_unref, see 'SubmitImages' method

        // 
        // post-process
        // 
        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(curInput->get(0));
        HVA_ASSERT(ptrFrameBuf);
        HceDatabaseMeta inputMeta;
        ptrFrameBuf->getMeta(inputMeta);
		
        AttributeContainer_t vecObjects;
        for (const auto& output : blobs) {
            std::string outputLayerName = output.first;
            InferenceBackend::OutputBlob::Ptr outputBlob = output.second;

            // dims: [N, ...], the first axis stands for batch
            auto dims = outputBlob->GetDims();
            size_t dataLength = outputBlob->GetSize() / dims[0];
            float* blobData = (float*)outputBlob->GetData() + batchIdx * dataLength;
            
            try {
                // find processor
                if (m_postProcessors.count(outputLayerName) || m_postProcessors.count("ANY")) {

                    ClassificationPostProcessor::Ptr processor;
                    if (m_postProcessors.count(outputLayerName))
                        processor = m_postProcessors[outputLayerName];
                    else
                        processor = m_postProcessors["ANY"];
                    ClassificationObject_t object = processor->process(blobData, dataLength);

                    std::string class_label = processor->getLabels().label_name(object.class_id);
                    object.label = class_label;
                    HVA_DEBUG("classification recognized: %s(%d): %f", object.label.c_str(), object.class_id, object.confidence);

                    // get attribute name
                    vecObjects.attr.emplace(processor->getAttributeName(), object);
                } else {
                    HVA_WARNING("%s failed to run post process on model output layer: %s!", 
                        m_nodeName.c_str(), outputLayerName.c_str());
                }
            } catch (const std::exception& e) {
                HVA_WARNING(
                    "%s failed to run post process on model output layer: %s, "
                    "error: %s!",
                    m_nodeName.c_str(), outputLayerName.c_str(), e.what());
            } catch (...) {
                HVA_WARNING(
                    "%s failed to run post process on model output layer: %s",
                    m_nodeName.c_str(), outputLayerName.c_str());
            }
        }

        // update meta for this input
        inputMeta.attributeResult.emplace(std::make_pair(inference_roi->roi.roi_id, vecObjects));
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
HVA_ENABLE_DYNAMIC_LOADING(ClassificationNode, ClassificationNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

} // namespace inference

} // namespace ai

} // namespace hce
