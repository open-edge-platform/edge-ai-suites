/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2024-2025 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
 */

#include <dirent.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <time.h>
#include <iostream>
#include <thread>
#include <vector>

#include <inc/util/hvaConfigStringParser.hpp>
#include "inference_nodes/base/baseImageInferenceNode.hpp"

namespace hce {

namespace ai {

namespace inference {

baseImageInferenceNode::baseImageInferenceNode(std::size_t totalThreadNum) : hva::hvaNode_t(1, 1, totalThreadNum)
{
    // init inference properties with default value
    m_inferenceProperties.device = DEFAULT_DEVICE;
    m_inferenceProperties.device_extensions = DEFAULT_DEVICE_EXTENSIONS;
    m_inferenceProperties.model_path = DEFAULT_MODEL_PATH;
    m_inferenceProperties.model_proc_config = DEFAULT_MODEL_PROC_CONFIG;
    m_inferenceProperties.model_proc_lib = DEFAULT_MODEL_PROC_LIB;
    m_inferenceProperties.inference_interval = DEFAULT_INFERENCE_INTERVAL;
    m_inferenceProperties.nireq = DEFAULT_NIREQ;
    m_inferenceProperties.pre_proc_type = DEFAULT_PRE_PROC_TYPE;
    m_inferenceProperties.allocator_name = DEFAULT_ALLOCATOR_NAME;

    // inference type
    m_inferenceProperties.inference_type = (InferenceType)DEFAULT_INFERENCE_TYPE;
    m_inferenceProperties.inference_region_type = (InferenceRegionType)DEFAULT_INFERENCE_REGION_TYPE;

    // model
    m_inferenceProperties.reshape_model_input = DEFAULT_RESHAPE_MODEL_INPUT;
    m_inferenceProperties.batch_size = DEFAULT_BATCH_SIZE;
    m_inferenceProperties.reshape_width = DEFAULT_RESHAPE_WIDTH;
    m_inferenceProperties.reshape_height = DEFAULT_RESHAPE_HEIGHT;

    // reset config parser
    m_configParser.reset();
}

baseImageInferenceNode::~baseImageInferenceNode() {}

/**
 * @brief initialization of this node. Init all inference properties with default value
 *
 * @param void
 * @return void
 *
 */
void baseImageInferenceNode::init() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 */
hva::hvaStatus_t baseImageInferenceNode::configureByString(const std::string &config)
{
    if (config.empty()) {
        return hva::hvaFailure;
    }

    if (!m_configParser.parse(config)) {
        HVA_ERROR("%s Illegal parse string!", nodeClassName().c_str());
        return hva::hvaFailure;
    }

    // models must be put in directory: "/opt/models/"
    std::string modelPath;
    m_configParser.getVal<std::string>("ModelPath", modelPath);
    if (modelPath.empty()) {
        HVA_ERROR("%s ModelPath must be configured!", nodeClassName().c_str());
        return hva::hvaFailure;
    }
    m_inferenceProperties.model_path = "/opt/models/" + modelPath;

    // model_proc configurations: *.model_proc.json
    // config files must be put in directory: "/opt/models/"
    std::string modelProcConfPath;
    m_configParser.getVal<std::string>("ModelProcConfPath", modelProcConfPath);
    if (!modelProcConfPath.empty()) {
        m_inferenceProperties.model_proc_config = "/opt/models/" + modelProcConfPath;
    }

    // customized library file: *.so
    std::string modelProcLibPath;
    m_configParser.getVal<std::string>("ModelProcLibPath", modelProcLibPath);
    if (!modelProcLibPath.empty()) {
        m_inferenceProperties.model_proc_lib = modelProcLibPath;
    }

    // infer request number, default as 2
    int numInferReq = 2;
    m_configParser.getVal<int>("InferReqNumber", numInferReq);
    m_inferenceProperties.nireq = (unsigned int)numInferReq;

    // inference batch size
    int batch_size = 1;
    m_configParser.getVal<int>("InferBatchSize", batch_size);
    m_inferenceProperties.batch_size = (unsigned int)batch_size;

    // openVINO param, e.g., InferConfig=(STRING_ARRAY)[CPU_THROUGHPUT_STREAMS=6,CPU_THREADS_NUM=6,CPU_BIND_THREAD=NUMA]
    std::vector<std::string> inference_config;
    m_configParser.getVal<std::vector<std::string>>("InferConfig", inference_config);
    m_inferenceProperties.inference_config = inference_config;

    std::vector<std::string> pre_proc_config;
    m_configParser.getVal<std::vector<std::string>>("PreProcessConfig", pre_proc_config);
    m_inferenceProperties.pre_proc_config = pre_proc_config;

    // inference device, default as "CPU"
    std::string inferDevice = "CPU";
    m_configParser.getVal<std::string>("Device", inferDevice);
    m_inferenceProperties.device = inferDevice;
    if (inferDevice.find("GPU") != std::string::npos) {
        if (inferDevice.rfind(".") == -1) {
            // "GPU", equals to "GPU.0"
            m_inferenceProperties.device_id = 0;
        }
        else {
            m_inferenceProperties.device_id = std::stoi(inferDevice.substr(inferDevice.rfind(".") + 1));
        }
        // m_inferenceProperties.device = "GPU";
    }
    else if (inferDevice == "CPU") {
        m_inferenceProperties.device_id = -1;
    }
    else if (inferDevice == "NPU") {
        m_inferenceProperties.device_id = 0;
    }
    else {
        return hva::hvaStatus_t::hvaFailure;
    }
    HVA_INFO("device_id: %d", m_inferenceProperties.device_id);

    int reshapeWidth = 0;
    int reshapeHeight = 0;
    m_configParser.getVal<int>("reshapeWidth", reshapeWidth);
    m_configParser.getVal<int>("reshapeHeight", reshapeHeight);
    m_inferenceProperties.reshape_width = (unsigned int)reshapeWidth;
    m_inferenceProperties.reshape_height = (unsigned int)reshapeHeight;
    HVA_INFO("reshapeWidth: %d", m_inferenceProperties.reshape_width);
    HVA_INFO("reshapeHeight: %d", m_inferenceProperties.reshape_height);

    int imageWidth = 0;
    int imageHeight = 0;
    m_configParser.getVal<int>("imageWidth", imageWidth);
    m_configParser.getVal<int>("imageHeight", imageHeight);
    m_inferenceProperties.image_width = (unsigned int)imageWidth;
    m_inferenceProperties.image_height = (unsigned int)imageHeight;
    HVA_INFO("imageWidth: %d", m_inferenceProperties.image_width);
    HVA_INFO("imageHeight: %d", m_inferenceProperties.image_height);

    // inference interval
    int inferenceInterval = 1;
    m_configParser.getVal<int>("InferenceInterval", inferenceInterval);
    m_inferenceProperties.inference_interval = (unsigned int)inferenceInterval;

    // preprocess engine type
    std::string preProcType = "ie";
    // std::string preProcType = "opencv";
    m_configParser.getVal<std::string>("PreProcessType", preProcType);
    m_inferenceProperties.pre_proc_type = preProcType;

    return hva::hvaStatus_t::hvaSuccess;
}

/**
 * @brief prepare and intialize this hvaNode_t instance. Create ImageInferenceInstance
 *
 * @param void
 * @return hvaSuccess if success
 */
hva::hvaStatus_t baseImageInferenceNode::prepare()
{
    // TODO
    // first manage va_display context (if has), for what??

    // acquire inference model instance
    try {
        m_inferenceInstance = createInferenceInstance(m_inferenceProperties);
    }
    catch (const std::exception &e) {
        HVA_ERROR("%s failed to create inference instance, error: %s!", nodeClassName().c_str(), e.what());
        return hva::hvaStatus_t::hvaFailure;
    }
    catch (...) {
        HVA_ERROR("%s failed to create inference instance!", nodeClassName().c_str());
        return hva::hvaStatus_t::hvaFailure;
    }

    if (!m_inferenceInstance) {
        HVA_ERROR("%s failed to create inference instance", nodeClassName().c_str());
        return hva::hvaStatus_t::hvaFailure;
    }
    HVA_DEBUG("%s created inference instance", nodeClassName().c_str());

    // Inference Engine preprocessing with batching is not supported
    if (m_inferenceProperties.batch_size > 1 && m_inferenceProperties.pre_proc_type == "ie") {
        m_inferenceProperties.pre_proc_type = "opencv";
        HVA_DEBUG("%s inference batch size: %d (> 1), change preprocess type from ie to opencv!", nodeClassName().c_str(), m_inferenceProperties.batch_size);
    }
    return hva::hvaStatus_t::hvaSuccess;
}

/**
 * @brief To perform any necessary operations when pipeline's rearm is called
 *
 * @param void
 * @return hvaSuccess if success
 *
 */
hva::hvaStatus_t baseImageInferenceNode::rearm()
{
    return hva::hvaStatus_t::hvaSuccess;
}

/**
 * @brief reset this node
 *
 * @param void
 * @return hvaSuccess if success
 *
 */
hva::hvaStatus_t baseImageInferenceNode::reset()
{
    return hva::hvaStatus_t::hvaSuccess;
}


ImageInferenceInstance::Ptr baseImageInferenceNode::createInferenceInstance(InferenceProperty &inferenceProperty)
{
    ImageInferenceInstance::Ptr instance = std::make_shared<ImageInferenceInstance>(inferenceProperty);
    return instance;
}

hva::hvaStatus_t baseImageInferenceNode::releaseInferenceInstance()
{
    return hva::hvaStatus_t::hvaSuccess;
}

baseImageInferenceNodeWorker::baseImageInferenceNodeWorker(hva::hvaNode_t *parentNode,
                                                           InferenceProperty inferenceProperty,
                                                           ImageInferenceInstance::Ptr instance)
    : hva::hvaNodeWorker_t(parentNode), m_inferenceProperties(inferenceProperty), m_inferenceInstance(instance)
{
    if (m_inferenceProperties.inference_type != InferenceType::HVA_NONE_TYPE) {
        // set callback for inference
        m_inferenceInstance->SetCallbackFunc(std::bind(&baseImageInferenceNodeWorker::processOutput, this, std::placeholders::_1, std::placeholders::_2),
                                             std::bind(&baseImageInferenceNodeWorker::processOutputFailed, this, std::placeholders::_1));
        m_inferenceInstance->CreateModel(m_inferenceProperties);
    }
}

baseImageInferenceNodeWorker::~baseImageInferenceNodeWorker() {}

/**
 * @brief Called by hva framework for each video frame, Run inference and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void baseImageInferenceNodeWorker::process(std::size_t batchIdx)
{
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

        for (auto &blob : inputs) {
            std::shared_ptr<hva::timeStampInfo> detectionIn = std::make_shared<hva::timeStampInfo>(blob->frameId, "detectionIn");
            getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &detectionIn);
            getLatencyMonitor().startRecording(blob->frameId, "inference");

            HVA_DEBUG("%s %d on frameId %d and streamid %u", m_nodeName.c_str(), batchIdx, blob->frameId, blob->streamId);
            hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(blob->get(0));

            // if (ptrFrameBuf->frameId < 5) {
            //     std::shared_ptr<hva::timeStampInfo> detectionIn = std::make_shared<hva::timeStampInfo>(blob->frameId, "detectionIn");
            //     getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &detectionIn);
            // }

            // TODO: repeat case?
            updateStreamEndFlags(blob->streamId, blob->frameId, ptrFrameBuf->getTag());

            if (validateInput(blob)) {
                int input_height = ptrFrameBuf->height;
                int input_width = ptrFrameBuf->width;

                //
                // run inference
                //
                getLatencyMonitor().startRecording(blob->frameId, "inference");
                InferenceStatus status = m_inferenceInstance->SubmitInference(m_inferenceProperties, blob);
                if (InferenceStatus::INFERENCE_NONE == status) {
                    HVA_DEBUG("%s skip processing at frameid %u and streamid %u: failed to submit inference!", m_nodeName.c_str(), blob->frameId,
                              blob->streamId);
                    HVA_DEBUG("%s sending blob with frameid %u and streamid %u", m_nodeName.c_str(), blob->frameId, blob->streamId);
                    sendOutput(blob, 0, std::chrono::milliseconds(0));
                    HVA_DEBUG("%s completed sent blob with frameid %u and streamid %u", m_nodeName.c_str(), blob->frameId, blob->streamId);
                }
                else if (InferenceStatus::INFERENCE_SKIPPED_ROI == status) {
                    HVA_DEBUG("%s skip processing at frameid %u and streamid %u: all rois are not selected!", m_nodeName.c_str(), blob->frameId,
                              blob->streamId);
                    HVA_DEBUG("%s sending blob with frameid %u and streamid %u", m_nodeName.c_str(), blob->frameId, blob->streamId);
                    sendOutput(blob, 0, std::chrono::milliseconds(0));
                    HVA_DEBUG("%s completed sent blob with frameid %u and streamid %u", m_nodeName.c_str(), blob->frameId, blob->streamId);
                }
                else {
                    // mark `depleting` status in hva pipeline
                    HVA_DEBUG("%s hold depleting on frameid %u and streamid %u", m_nodeName.c_str(), blob->frameId, blob->streamId);
                    getParentPtr()->holdDepleting();
                    //
                    // InferenceStatus::INFERENCE_EXECUTED == status
                    //
                    // This async inference is successfully executed.
                    // The specific inference node would call the processOutput() once inference done
                }
            }

            // flush all inference request equeue
            if (needFlushInference(blob->streamId)) {
                HVA_DEBUG("%s flush all inference requests on frameid %u and streamid %u", m_nodeName.c_str(), blob->frameId, blob->streamId);
                m_inferenceInstance->FlushInference();
            }
        }
    }
    catch (const std::exception &e) {
        HVA_ERROR("%s failed on frame processing, error: %s", m_nodeName.c_str(), e.what());
    }
    catch (...) {
        HVA_ERROR("%s failed on frame processing", m_nodeName.c_str());
    }
}

hva::hvaStatus_t baseImageInferenceNodeWorker::reset()
{
    m_inputBlobs.clear();
    return hva::hvaStatus_t::hvaSuccess;
}

/**
 * @brief would be called at the end of each process() to send outputs to the
 * downstream nodes if inference failed
 * @return void
 */
void baseImageInferenceNodeWorker::processOutputFailed(std::vector<std::shared_ptr<InferenceBackend::ImageInference::IFrameBase>> frames)
{
    HVA_WARNING("%s processOutput in failed case", m_nodeName.c_str());
    if (frames.size() == 0) {
        HVA_ERROR("%s received none inference results!", m_nodeName.c_str());
        HVA_ASSERT(false);
    }
    size_t batchSize = frames.size();

    // directly send out the input, do not process the inference results
    for (size_t batchIdx = 0; batchIdx < batchSize; batchIdx++) {
        auto inference_result = std::dynamic_pointer_cast<ImageInferenceInstance::InferenceResult>(frames[batchIdx]);
        /* InferenceResult is inherited from IFrameBase */
        assert(inference_result.get() != nullptr && "Expected a valid InferenceResult");

        hva::hvaBlob_t::Ptr curInput = inference_result->input;
        HVA_DEBUG("%s processed output on frameid %u and streamid %u", m_nodeName.c_str(), curInput->frameId, curInput->streamId);
        m_inputBlobs.put(curInput);

        inference_result->image.reset();  // deleter will to not make buffer_unref, see 'SubmitImages' method

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
        }
    }
}

void baseImageInferenceNodeWorker::updateStreamEndFlags(unsigned streamId, unsigned frameId, unsigned tag)
{
    if (m_streamEndFlags.count(streamId) == 0) {
        // init the frame counter for current streamId
        // the last frame has not been decided yet, makr as -1.
        m_streamEndFlags.emplace(streamId, std::make_pair(-1, 0));
    }
    if (tag == hvaBlobBufferTag::END_OF_REQUEST) {
        m_streamEndFlags[streamId].first = frameId;
    }
    m_streamEndFlags[streamId].second++;
}

bool baseImageInferenceNodeWorker::needFlushInference(unsigned streamId)
{
    if (m_streamEndFlags.count(streamId)) {
        // frameId starts from 0
        return m_streamEndFlags[streamId].second == (m_streamEndFlags[streamId].first + 1);
    }
    else {
        return false;
    }
}

/**
 * @brief collect all inputs from each port of hvaNode.
 *
 * @return std::vector<std::vector<hva::hvaBlob_t>>
 */
std::vector<std::vector<hva::hvaBlob_t::Ptr>> baseImageInferenceNodeWorker::getInput(std::size_t batchIdx)
{
    std::vector<std::vector<hva::hvaBlob_t::Ptr>> collectedInputs;

    // get input blob from port 0
    std::vector<hva::hvaBlob_t::Ptr> vecBlobInput = getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0}, std::chrono::milliseconds(1000));
    collectedInputs.push_back(vecBlobInput);

    return collectedInputs;
}

/**
 * @brief validate input
 * @param blob current input
 * @return if process need continue
 *
 */
bool baseImageInferenceNodeWorker::validateInput(hva::hvaBlob_t::Ptr &blob)
{
    //
    // for sanity check
    //
    hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(blob->get(0));
    HVA_ASSERT(ptrFrameBuf);

    HceDatabaseMeta inputMeta;
    ptrFrameBuf->getMeta(inputMeta);
    InferenceTimeStamp_t inferenceTimeMeta;
    if (ptrFrameBuf->getMeta(inferenceTimeMeta) == hva::hvaSuccess) {
        HVA_DEBUG("BaseImageInferenceNode get inferenceTimeMeta from input buffer");
        std::chrono::time_point<std::chrono::high_resolution_clock> currentTime = std::chrono::high_resolution_clock::now();
        inferenceTimeMeta.endTime = currentTime;
        ptrFrameBuf->setMeta(inferenceTimeMeta);
    }

    //
    // pre-check
    //
    if (ptrFrameBuf->drop) {
        // coming empty buf
        ptrFrameBuf->rois.clear();

        HVA_DEBUG("%s dropped a frame on frameid %u and streamid %u", m_nodeName.c_str(), blob->frameId, blob->streamId);
        HVA_DEBUG("%s sending blob with frameid %u and streamid %u", m_nodeName.c_str(), blob->frameId, blob->streamId);
        sendOutput(blob, 0, std::chrono::milliseconds(0));
        HVA_DEBUG("%s completed sent blob with frameid %u and streamid %u", m_nodeName.c_str(), blob->frameId, blob->streamId);
        return false;
    }
    else if (m_inferenceProperties.inference_interval > 1 && blob->frameId % m_inferenceProperties.inference_interval != 0) {
        // skip frame if m_inferenceProperties.inference_interval is defined > 1
        ptrFrameBuf->rois.clear();

        HVA_DEBUG("%s skip processing at frameid %u and streamid %u", m_nodeName.c_str(), blob->frameId, blob->streamId);
        HVA_DEBUG("%s sending blob with frameid %u and streamid %u", m_nodeName.c_str(), blob->frameId, blob->streamId);
        sendOutput(blob, 0, std::chrono::milliseconds(0));
        HVA_DEBUG("%s completed sent blob with frameid %u and streamid %u", m_nodeName.c_str(), blob->frameId, blob->streamId);
        return false;
    }
    else if (ptrFrameBuf->rois.size() == 0 && m_inferenceProperties.inference_region_type == InferenceRegionType::ROI_LIST) {
        // if none rois are received, no need to do inference type: ROI_LIST.
        HVA_DEBUG("No ROI is provided on frameid %u at %s. Skipping...", blob->frameId, m_nodeName.c_str());
        HVA_DEBUG("%s sending blob with frameid %u and streamid %u", m_nodeName.c_str(), blob->frameId, blob->streamId);
        sendOutput(blob, 0, std::chrono::milliseconds(0));
        HVA_DEBUG("%s completed sent blob with frameid %u and streamid %u", m_nodeName.c_str(), blob->frameId, blob->streamId);
        return false;
    }

    int input_height = ptrFrameBuf->height;
    int input_width = ptrFrameBuf->width;

    // special case, using whole image as one roi, and run inference for it
    // input param should be: [0, 0, 0, 0]
    if (m_inferenceProperties.inference_region_type == InferenceRegionType::ROI_LIST && ptrFrameBuf->rois.size() == 1) {
        hva::hvaROI_t tmpROI = ptrFrameBuf->rois[0];
        if (tmpROI.x == 0 && tmpROI.y == 0 && tmpROI.width == 0 && tmpROI.height == 0) {
            // use full image as input roi
            ptrFrameBuf->rois.clear();
            tmpROI.width = input_width;
            tmpROI.height = input_height;
            ptrFrameBuf->rois.push_back(tmpROI);
        }
    }
    return true;
}

}  // namespace inference

}  // namespace ai

}  // namespace hce
