/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2025 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
 */

#include <boost/exception/all.hpp>

#include <cstddef>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>

#include "nodes/CPU-backend/LidarCamFusionInputNode.hpp"

#include <thread>
#include "modules/inference_util/lidar/kitti_loader.hpp"

namespace hce {

namespace ai {

namespace inference {

LidarCamFusionInputNode::LidarCamFusionInputNode(std::size_t totalThreadNum) : hva::hvaNode_t(1, 1, totalThreadNum) {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 */
hva::hvaStatus_t LidarCamFusionInputNode::configureByString(const std::string &config)
{
    if (config.empty())
        return hva::hvaFailure;

    if (!m_configParser.parse(config)) {
        HVA_ERROR("Illegal parse string!");
        return hva::hvaFailure;
    }

    std::string dataSource = "vehicle";
    m_configParser.getVal<std::string>("DataSource", dataSource);
    m_dataSource = dataSource;

    // configure media/radar/calib input indices
    m_configParser.getVal<int>("MediaIndex", m_sensorIndices.mediaIndex);
    m_configParser.getVal<int>("LidarIndex", m_sensorIndices.lidarIndex);
    m_configParser.getVal<int>("CalibIndex", m_sensorIndices.calibIndex);
    if (m_sensorIndices.mediaIndex >= DEFAULT_MULTI_SENSOR_INPUT_NUM || m_sensorIndices.lidarIndex >= DEFAULT_MULTI_SENSOR_INPUT_NUM ||
        m_sensorIndices.calibIndex >= DEFAULT_MULTI_SENSOR_INPUT_NUM) {
        HVA_ERROR("Input sensor index must be smaller than %d, receiving mediaIndex: %d!, RadarIndex: %d, CalibIndex: %d", DEFAULT_MULTI_SENSOR_INPUT_NUM,
                  m_sensorIndices.mediaIndex, m_sensorIndices.lidarIndex, m_sensorIndices.calibIndex);
        return hva::hvaFailure;
    }

    int inputCapacity = 0;
    m_configParser.getVal<int>("InputCapacity", inputCapacity);
    m_inputCapacity = inputCapacity;

    int stride = 1;
    m_configParser.getVal<int>("Stride", stride);
    m_stride = stride;

    float frameRate = 0.0;
    m_configParser.getVal<float>("FrameRate", frameRate);
    m_frameRate = frameRate;

    std::string controlType = "Video";
    m_configParser.getVal<std::string>("ControlType", controlType);
    m_controlType = controlType;

    std::string sensorType = "All";
    m_configParser.getVal<std::string>("SensorType", sensorType);
    m_sensorType = sensorType;

    transitStateTo(hva::hvaState_t::configured);
    return hva::hvaSuccess;
}

std::shared_ptr<hva::hvaNodeWorker_t> LidarCamFusionInputNode::createNodeWorker() const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(
        new LidarCamFusionInputNodeWorker((hva::hvaNode_t *)this, m_sensorIndices, m_inputCapacity, m_stride, m_frameRate, m_controlType, m_sensorType));
}


LidarCamFusionInputNodeWorker::LidarCamFusionInputNodeWorker(hva::hvaNode_t *parentNode,
                                                             const LidarCamFusionInputNode::InpustSensorIndices_t &sensorIndices,
                                                             const size_t &inputCapacity,
                                                             const size_t &stride,
                                                             const float &frameRate,
                                                             const std::string &controlType,
                                                             const std::string &sensorType)
    : hva::hvaNodeWorker_t(parentNode), m_ctr(0u), m_sensorIndices(sensorIndices), m_inputCapacity(inputCapacity), m_stride(stride), m_frameRate(frameRate),
      m_controlType(controlType), m_sensorType(sensorType), m_workStreamId(-1)
{
    m_controllerMap[0] = std::make_shared<SendController>(inputCapacity, stride, controlType);
}

void LidarCamFusionInputNodeWorker::process(std::size_t batchIdx)
{
    // get input blob from port0
    auto vecBlobInput = getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});

    if (vecBlobInput.size() != 0) {
        hva::hvaBlob_t::Ptr inBlob = vecBlobInput[0];
        HVA_DEBUG("Local CPlusL Sensor Input node %d on frameId %d", batchIdx, inBlob->frameId);

        getParentPtr()->emitEvent(hvaEvent_PipelineLatencyCapture, &inBlob->frameId);
        std::shared_ptr<hva::timeStampInfo> inputNodeIn = std::make_shared<hva::timeStampInfo>(inBlob->frameId, "InputNodeIn");
        getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &inputNodeIn);

        hva::hvaBuf_t::Ptr buf = inBlob->get(0);
        std::vector<std::string> comingInputs = buf->get<std::vector<std::string>>();

        size_t multiSensorInputNum = DEFAULT_MULTI_SENSOR_INPUT_NUM;  // default for lidar and media
        if (m_sensorType == "All") {
            multiSensorInputNum = DEFAULT_MULTI_SENSOR_INPUT_NUM;
        }
        else if (m_sensorType == "Media") {
            multiSensorInputNum = 1;
        }
        else if (m_sensorType == "Lidar") {
            multiSensorInputNum = 2;
        }
        else {
            HVA_ERROR("Unsupported sensor type: %s, only support Media, Lidar and All", m_sensorType.c_str());
            HceDatabaseMeta meta;
            sendEmptyBlob(inBlob, true, meta);
            return;
        }

        // for sanity
        int streamId = (int)inBlob->streamId;
        if (comingInputs.size() == 0 || comingInputs.size() % multiSensorInputNum != 0) {
            HVA_ERROR("Local MultiSensor Input node %d received invalid inputs length: %d on frame %d, should be a multiple of %d", batchIdx,
                      comingInputs.size(), inBlob->frameId, multiSensorInputNum);

            HceDatabaseMeta meta;
            sendEmptyBlob(inBlob, true, meta);
            return;
        }
        else if (m_workStreamId >= 0 && streamId != m_workStreamId) {
            HVA_ERROR("Input worker should work on streamId: %d, but received "
                      "data from invalid streamId: %d!",
                      m_workStreamId, streamId);
            // send output
            HceDatabaseMeta meta;
            sendEmptyBlob(inBlob, true, meta);
            return;
        }
        else {
            m_workStreamId = streamId;
        }

        // processing multiple coming medias, send to specified port in sequence
        for (int inputIdx = 0; inputIdx < comingInputs.size(); inputIdx += multiSensorInputNum) {
            std::shared_ptr<hva::timeStampInfo> lidarInputIn = std::make_shared<hva::timeStampInfo>(inBlob->frameId, "LidarInputIn");
            getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &lidarInputIn);

            // the last request input will be taged as end
            bool isEnd = (inputIdx >= comingInputs.size() - multiSensorInputNum);

            /**
             * process input content
             */
            MultiSensorField_t content;
            CalibField_t calibContent;
            HceDatabaseMeta meta;
            hva::hvaROI_t roi;
            unsigned x = 0, y = 0, w = 0, h = 0;
            roi.x = x;
            roi.y = y;
            roi.width = w;
            roi.height = h;

            auto blob = hva::hvaBlob_t::make_blob();
            blob->streamId = batchIdx;
            blob->frameId = fetch_increment();

            for (int idx = 0; idx < multiSensorInputNum; idx++) {
                std::string path = comingInputs[inputIdx + idx];
                // read binary data

                // image
                if (idx == m_sensorIndices.mediaIndex) {
                    // media data
                    if (!getImageFromPath(path, content.imageContent, content.imageSize)) {
                        HVA_ERROR("Failed to read image data from %s", path.c_str());
                        sendEmptyBlob(inBlob, isEnd, meta);
                        return;
                    }
                }
                // lidar
                else if (idx == m_sensorIndices.lidarIndex) {
                    // lidar data
                    if (!getPointCloudFromPath(path, content.lidarContent)) {
                        HVA_ERROR("Failed to read lidar data from %s", path.c_str());
                        sendEmptyBlob(inBlob, isEnd, meta);
                        return;
                    }
                    content.lidarSize = content.lidarContent.size();
                }
                // calibration
                else if (idx == m_sensorIndices.calibIndex) {
                    // calibration data
                    if (!getCalibrationFromPath(path, calibContent.transforms, calibContent.cameraParams)) {
                        HVA_ERROR("Failed to read calibration data from %s", path.c_str());
                        sendEmptyBlob(inBlob, isEnd, meta);
                        return;
                    }
                }
                else {
                    HVA_ERROR("Unsupported sensor index: %d", idx);
                    sendEmptyBlob(inBlob, isEnd, meta);
                    return;
                }
            }

            HVA_DEBUG("media content size is : %d on frameid %d streamid %d", content.imageSize, blob->frameId, blob->streamId);
            HVA_DEBUG("lidar content size is : %d on frameid %d streamid %d", content.lidarSize, blob->frameId, blob->streamId);
            HVA_DEBUG("calib transforms size is : %d on frameid %d streamid %d", calibContent.transforms.size(), blob->frameId, blob->streamId);

            // make buffer for blob
            auto jpgHvaBuf = hva::hvaVideoFrameWithROIBuf_t::make_buffer<std::string>(content.imageContent, content.imageSize);
            jpgHvaBuf->rois.push_back(std::move(roi));
            auto lidarHvaBuf = hva::hvaVideoFrameWithROIBuf_t::make_buffer<lidarVec_t>(content.lidarContent, content.lidarSize);

            // mark buffer as empty if content is null
            if (m_sensorType == "Media" && content.imageSize == 0) {
                jpgHvaBuf->drop = true;
                lidarHvaBuf->drop = true;
            }
            else if (m_sensorType == "Lidar" && content.lidarSize == 0) {
                jpgHvaBuf->drop = true;
                lidarHvaBuf->drop = true;
            }
            else if (m_sensorType == "All" && (content.imageSize == 0 || content.lidarSize == 0 || calibContent.transforms.empty())) {
                // both media and lidar data should be present
                jpgHvaBuf->drop = true;
                lidarHvaBuf->drop = true;
            }

            if (isEnd) {
                // last one in the batch. Mark it
                HVA_DEBUG("Set tag 1 on frame %d", blob->frameId);
                jpgHvaBuf->tagAs(1);
                lidarHvaBuf->tagAs(1);
            }
            else {
                jpgHvaBuf->tagAs(0);
                lidarHvaBuf->tagAs(0);
            }

            if (streamId == m_workStreamId && m_controllerMap.find(m_workStreamId) == m_controllerMap.end() && 0 < m_inputCapacity) {
                // key not exists, construct it
                m_controllerMap[m_workStreamId] = std::make_shared<SendController>(m_inputCapacity, m_stride, m_controlType);
            }

            if ((streamId == m_workStreamId) && (0 < m_inputCapacity)) {
                std::unique_lock<std::mutex> lock(m_controllerMap[m_workStreamId]->mtx);
                while (m_controllerMap[m_workStreamId]->count > (m_inputCapacity - 1) * m_stride) {
                    (m_controllerMap[m_workStreamId]->notFull).wait(lock);
                }
                (m_controllerMap[m_workStreamId]->count) += m_stride;
                lock.unlock();
                jpgHvaBuf->setMeta(m_controllerMap[m_workStreamId]);
                lidarHvaBuf->setMeta(m_controllerMap[m_workStreamId]);
            }

            jpgHvaBuf->setMeta(meta);
            jpgHvaBuf->setMeta(calibContent);
            lidarHvaBuf->setMeta(meta);
            lidarHvaBuf->setMeta(calibContent);
            jpgHvaBuf->frameId = blob->frameId;
            lidarHvaBuf->frameId = blob->frameId;
            HVA_DEBUG("Multi input source node sets meta to buffer");

            blob->push(jpgHvaBuf);
            blob->push(lidarHvaBuf);
            sendOutput(blob, 0, std::chrono::milliseconds(0));
            // auto now = std::chrono::high_resolution_clock::now();
            // auto epoch = now.time_since_epoch();
            // auto milliseconds = std::chrono::duration_cast<std::chrono::milliseconds>(epoch).count();
            HVA_INFO("Multi input source node push the %d th jpeg data to blob", blob->frameId);
            // HVA_INFO("Multi input source node push the %d th jpeg data to blob on time %d", blob->frameId, milliseconds);
            if ((streamId == m_workStreamId) && (0 >= m_inputCapacity || (m_controllerMap[m_workStreamId]->count > (m_inputCapacity - 1) * m_stride)) &&
                (0 != inputIdx) && (0.0 != m_frameRate)) {
                std::this_thread::sleep_for(std::chrono::milliseconds(int(1000 / m_frameRate)));
            }
            std::shared_ptr<hva::timeStampInfo> lidarInputOut = std::make_shared<hva::timeStampInfo>(inBlob->frameId, "LidarInputOut");
            getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &lidarInputOut);
        }
        std::shared_ptr<hva::timeStampInfo> inputOut = std::make_shared<hva::timeStampInfo>(inBlob->frameId, "InputNodeOut");
        getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &inputOut);
    }
}

/**
 * @brief Frame index increased for every coming frame, will be called at the process()
 * @param void
 */
unsigned LidarCamFusionInputNodeWorker::fetch_increment()
{
    return m_ctr++;
}

/**
 * @brief Send empty buf to next node
 * @param blob input blob data with empty buf
 * @param isEnd flag for coming request
 * @param meta databaseMeta
 */
void LidarCamFusionInputNodeWorker::sendEmptyBlob(hva::hvaBlob_t::Ptr blob, bool isEnd, const HceDatabaseMeta &meta)
{
    blob->vBuf.clear();
    auto jpgHvaBuf = hva::hvaVideoFrameWithROIBuf_t::make_buffer<std::string>(std::string(), 0);
    auto lidarHvaBuf = hva::hvaVideoFrameWithROIBuf_t::make_buffer<lidarVec_t>(lidarVec_t(), 0);

    // drop mark as true for empty blob
    jpgHvaBuf->drop = true;
    lidarHvaBuf->drop = true;

    if (isEnd) {
        // last one in the batch. Mark it
        HVA_DEBUG("Set tag 1 on frame %d", blob->frameId);
        jpgHvaBuf->tagAs(1);
        lidarHvaBuf->tagAs(1);
    }
    else {
        jpgHvaBuf->tagAs(0);
        lidarHvaBuf->tagAs(0);
    }

    jpgHvaBuf->setMeta(meta);
    lidarHvaBuf->setMeta(meta);
    blob->push(jpgHvaBuf);
    blob->push(lidarHvaBuf);

    sendOutput(blob, 0, std::chrono::milliseconds(0));
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(LidarCamFusionInputNode, LidarCamFusionInputNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce
