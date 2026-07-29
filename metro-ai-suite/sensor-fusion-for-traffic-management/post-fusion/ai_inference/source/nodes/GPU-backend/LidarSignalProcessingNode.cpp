/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2023-2024 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
 */

#include <algorithm>
#include <cmath>
#include <condition_variable>

#include <inc/util/hvaConfigStringParser.hpp>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>
#include <inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp>

#include "nodes/GPU-backend/LidarSignalProcessingNode.hpp"
#include <boost/exception/all.hpp>

#include "common/base64.hpp"
#include "nodes/databaseMeta.hpp"
#include "nodes/lidarDatabaseMeta.hpp"
#include "liblidar.hpp"
#include <memory>
#include <queue>
#include <mutex>
#include <thread>

namespace hce {

namespace ai {

namespace inference {


class PointPillarsPool {
  public:
    PointPillarsPool(size_t poolSize, float scoreThreshold, float nmsThreshold, const pointpillars::PointPillarsConfig &config, const std::string &device)
    {
        for (size_t i = 0; i < poolSize; ++i) {
            pool_.push(std::make_unique<pointpillars::PointPillars>(scoreThreshold, nmsThreshold, config, device));
        }
    }

    pointpillars::PointPillars *acquire()
    {
        std::unique_lock<std::mutex> lock(mtx_);
        cond_.wait(lock, [this] { return !pool_.empty(); });
        auto ptr = pool_.front().release();
        pool_.pop();
        return ptr;
    }

    void release(pointpillars::PointPillars *inst)
    {
        std::lock_guard<std::mutex> lock(mtx_);
        pool_.push(std::unique_ptr<pointpillars::PointPillars>(inst));
        cond_.notify_one();
    }

  private:
    std::queue<std::unique_ptr<pointpillars::PointPillars>> pool_;
    std::mutex mtx_;
    std::condition_variable cond_;
};

static std::unique_ptr<PointPillarsPool> g_pointpillarsPool;
static std::once_flag g_poolInitFlag;

class LidarSignalProcessingNode::Impl {
  public:
    Impl(LidarSignalProcessingNode &ctx);

    ~Impl();

    /**
     * @brief Parse params, called by hva framework right after node instantiate.
     * @param config Configure string required by this node.
     */
    hva::hvaStatus_t configureByString(const std::string &config);

    /**
     * @brief To validate ModelPath in configure is not none.
     * @param void
     */
    hva::hvaStatus_t validateConfiguration() const;

    /**
     * @brief Constructs and returns a node worker instance: ClassificationNodeWorker_CPU.
     * @param void
     */
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(LidarSignalProcessingNode *parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

  private:
    LidarSignalProcessingNode &m_ctx;

    hva::hvaConfigStringParser_t m_configParser;

    pointpillars::PointPillarsConfig m_lidarConfig;
    float m_scoreThreshold;
    float m_nmsThreshold;
    std::string m_device;

    // LidarPreProcessingNode::Ptr m_model;
};

LidarSignalProcessingNode::Impl::Impl(LidarSignalProcessingNode &ctx) : m_ctx(ctx)
{
    m_configParser.reset();
}

LidarSignalProcessingNode::Impl::~Impl() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 */
hva::hvaStatus_t LidarSignalProcessingNode::Impl::configureByString(const std::string &config)
{
    // parse json file and save data to LidarConfigParam
    if (config.empty()) {
        return hva::hvaFailure;
    }

    if (!m_configParser.parse(config)) {
        HVA_ERROR("Illegal parse string!");
    }

    // models must be put in directory: "/opt/models/"
    std::string lidarConfigPath;
    m_configParser.getVal<std::string>("LidarConfigPath", lidarConfigPath);
    HVA_DEBUG("lidarConfigPath (%s) read", lidarConfigPath.c_str());

    // parser json

    // HVA_DEBUG("Parsing model_proc json from file: %s", lidarConfigPath.c_str());
    JsonReader m_json_reader;
    m_json_reader.read(lidarConfigPath);
    const nlohmann::json &lidar_config_content = m_json_reader.content();
    std::vector<std::string> required_fields = {"PointPillarsConfig"};
    JsonReader::check_required_item(lidar_config_content, required_fields);

    // read PointPillarsConfig
    auto pointpillars_config_items = lidar_config_content.at("PointPillarsConfig");
    for (auto &items : pointpillars_config_items) {
        m_lidarConfig.min_x_range = items["min_x_range"].get<float>();
        m_lidarConfig.max_x_range = items["max_x_range"].get<float>();
        m_lidarConfig.min_y_range = items["min_y_range"].get<float>();
        m_lidarConfig.max_y_range = items["max_y_range"].get<float>();
        m_lidarConfig.min_z_range = items["min_z_range"].get<float>();
        m_lidarConfig.max_z_range = items["max_z_range"].get<float>();
        m_lidarConfig.rpn_scale = items["rpn_scale"].get<float>();
        m_lidarConfig.pillar_x_size = items["pillar_x_size"].get<float>();
        m_lidarConfig.pillar_y_size = items["pillar_y_size"].get<float>();
        m_lidarConfig.pillar_z_size = items["pillar_z_size"].get<float>();
        m_lidarConfig.x_stride = items["x_stride"].get<float>();
        m_lidarConfig.y_stride = items["y_stride"].get<float>();
        m_lidarConfig.max_num_pillars = items["max_num_pillars"].get<int>();
        m_lidarConfig.num_classes = items["num_classes"].get<int>();
        std::vector<float> anchor = items["anchors"].get<std::vector<float>>();
        m_lidarConfig.anchors = {pointpillars::Anchor(anchor[0], anchor[1], anchor[2])};
        m_lidarConfig.classes = items["classes"].get<std::vector<std::string>>();
        m_lidarConfig.max_num_points_per_pillar = items["max_num_points_per_pillar"].get<int>();
        m_lidarConfig.pillar_features = items["pillar_features"].get<int>();
        m_lidarConfig.grid_x_size = items["grid_x_size"].get<int>();
        m_lidarConfig.grid_y_size = items["grid_y_size"].get<int>();
        m_lidarConfig.grid_z_size = items["grid_z_size"].get<int>();
    }


    std::string pfe_model_file;
    m_configParser.getVal<std::string>("PfeModelFile", pfe_model_file);
    std::string rpn_model_file;
    m_configParser.getVal<std::string>("RpnModelFile", rpn_model_file);
    if (pfe_model_file.empty() || rpn_model_file.empty()) {
        HVA_ERROR("PfeModelFile or RpnModelFile is empty");
        return hva::hvaFailure;
    }
    m_lidarConfig.pfe_model_file = pfe_model_file;
    m_lidarConfig.rpn_model_file = rpn_model_file;

    float scoreThreshold = 0.5;
    m_configParser.getVal<float>("ScoreThreshold", scoreThreshold);
    m_scoreThreshold = scoreThreshold;

    float nmsThreshold = 0.5;
    m_configParser.getVal<float>("NmsThreshold", nmsThreshold);
    m_nmsThreshold = nmsThreshold;

    std::string device = "CPU";
    m_configParser.getVal<std::string>("Device", device);
    if (device.empty()) {
        HVA_ERROR("Device is empty");
        return hva::hvaFailure;
    }
    m_device = device;

    // after all configures being parsed, this node should be trainsitted to `configured`
    m_ctx.transitStateTo(hva::hvaState_t::configured);

    return hva::hvaSuccess;
}

/**
 * @brief Constructs and returns a node worker instance: ClassificationNodeWorker_CPU.
 * @param void
 */
std::shared_ptr<hva::hvaNodeWorker_t> LidarSignalProcessingNode::Impl::createNodeWorker(LidarSignalProcessingNode *parent) const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>{new LidarSignalProcessingNodeWorker{parent, m_scoreThreshold, m_nmsThreshold, m_device, m_lidarConfig}};
}

hva::hvaStatus_t LidarSignalProcessingNode::Impl::rearm()
{
    // to-do:
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarSignalProcessingNode::Impl::reset()
{
    // to-do:
    return hva::hvaSuccess;
}

LidarSignalProcessingNode::LidarSignalProcessingNode(std::size_t totalThreadNum) : hva::hvaNode_t(1, 1, totalThreadNum), m_impl(new Impl(*this))
{
    // transitStateTo(hva::hvaState_t::configured);
}

LidarSignalProcessingNode::~LidarSignalProcessingNode() {}

hva::hvaStatus_t LidarSignalProcessingNode::configureByString(const std::string &config)
{
    return m_impl->configureByString(config);
}

std::shared_ptr<hva::hvaNodeWorker_t> LidarSignalProcessingNode::createNodeWorker() const
{
    return m_impl->createNodeWorker(const_cast<LidarSignalProcessingNode *>(this));
}

hva::hvaStatus_t LidarSignalProcessingNode::rearm()
{
    return m_impl->rearm();
}

hva::hvaStatus_t LidarSignalProcessingNode::reset()
{
    return m_impl->reset();
}

class LidarSignalProcessingNodeWorker::Impl {
  public:
    Impl(LidarSignalProcessingNodeWorker &ctx,
         float scoreThreshold,
         float nmsThreshold,
         std::string device,
         const pointpillars::PointPillarsConfig &lidarConfig);

    ~Impl();

    /**
     * @brief Called by hva framework for each video frame, Run inference and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx);

    void init();

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

  private:
    /**
     * @brief run post processing on model outputs
     * @param layerName output layer name
     * @param ptrBlob source output data for classification model
     * @param object ClassificationObject_t, saving parsed results
     * @return boolean
    //  */
    // bool runPostproc(const std::string layerName, const InferenceEngine::Blob::Ptr &ptrBlob, ClassificationObject_t &object);

    LidarSignalProcessingNodeWorker &m_ctx;

    pointpillars::PointPillarsConfig m_lidarConfig;
    float m_scoreThreshold;
    float m_nmsThreshold;
    std::string m_device;

    pointpillars::PointPillars *m_pointpillars;
};

LidarSignalProcessingNodeWorker::Impl::Impl(LidarSignalProcessingNodeWorker &ctx,
                                            float scoreThreshold,
                                            float nmsThreshold,
                                            std::string device,
                                            const pointpillars::PointPillarsConfig &lidarConfig)
    : m_ctx(ctx), m_scoreThreshold(scoreThreshold), m_nmsThreshold(nmsThreshold), m_device(device), m_lidarConfig(lidarConfig)
{
    HVA_INFO("Running on GPU device: %s", m_device.c_str());

    m_pointpillars = nullptr;
    m_pointpillars = new pointpillars::PointPillars(m_scoreThreshold, m_nmsThreshold, m_lidarConfig, m_device);
    // m_pointpillars = pointpillars::PointPillars::getInstance(m_scoreThreshold, m_nmsThreshold, m_lidarConfig, m_device);
    if (!m_pointpillars) {
        HVA_ERROR("Failed to create PointPillars instance");
        throw std::runtime_error("Failed to create PointPillars instance");
    }

    // std::call_once(g_poolInitFlag, [&]() { g_pointpillarsPool = std::make_unique<PointPillarsPool>(1, scoreThreshold, nmsThreshold, lidarConfig, device); });
}

LidarSignalProcessingNodeWorker::Impl::~Impl()
{
    if (m_pointpillars) {
        delete m_pointpillars;
        m_pointpillars = nullptr;
    }
}

/**
 * @brief Called by hva framework for each video frame, Run inference and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void LidarSignalProcessingNodeWorker::Impl::process(std::size_t batchIdx)
{
    // get input blob from port 0
    auto vecBlobInput = m_ctx.getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});

    // input blob is not empty
    if (vecBlobInput.size() != 0) {
        std::chrono::time_point<std::chrono::high_resolution_clock> currentTime;
        currentTime = std::chrono::high_resolution_clock::now();
        LidarTimeStamp_t lidarTimeMeta;
        lidarTimeMeta.startTime = currentTime;

        hva::hvaBlob_t::Ptr blob = vecBlobInput[0];
        HVA_ASSERT(blob);
        HVA_DEBUG("Lidar Signal Processing node %d on frameId %d", batchIdx, blob->frameId);
        std::shared_ptr<hva::timeStampInfo> LidarSignalProcessingIn = std::make_shared<hva::timeStampInfo>(blob->frameId, "LidarSignalProcessingIn");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &LidarSignalProcessingIn);

        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(blob->get(1));


        unsigned tag = ptrFrameBuf->getTag();
        if (!ptrFrameBuf->drop) {
            HVA_DEBUG("Lidar signal processing start processing %d frame with tag %d", blob->frameId, tag);
            std::vector<pointpillars::ObjectDetection> objectDetections;

            lidarVec_t lidarPoints = ptrFrameBuf->get<lidarVec_t>();

            size_t frameSize = ptrFrameBuf->getSize();  // frame_data_size

            // frameSize is the total number of float elements in lidarVec_t (std::vector<float>)
            // Each point contains 4 float values (x, y, z, intensity)
            size_t numPoints = frameSize / 4;

            if (numPoints == 0) {
                HVA_ERROR("Lidar signal processing on frame%d, unable to read point cloud file.", blob->frameId);
                return;
            }
            else {
                HVA_DEBUG("Lidar signal processing on frame%d, frame[0]: %zu points", blob->frameId, numPoints);
            }

            size_t dur[6];
            memset(dur, 0, sizeof(size_t) * 6);
            // m_pointpillars = g_pointpillarsPool->acquire();
            // if (!m_pointpillars) {
            //     HVA_ERROR("No available PointPillars instance in pool");
            //     return;
            // }
            try {
                m_pointpillars->Detect(lidarPoints.data(), numPoints, objectDetections, dur);
            }
            catch (const std::runtime_error &e) {
                HVA_ERROR("Exception during PointPillars execution: %s", e.what());
            }

            // g_pointpillarsPool->release(m_pointpillars);

            HVA_INFO("object detected: %d", objectDetections.size());
            // for (auto const &detection : objectDetections) {
            //     HVA_INFO("class_id: %d, class_probabilities: %f, x: %f, y: %f, z: %f, length: %f, width: %f", detection.class_id,
            //              detection.class_probabilities[0], detection.x, detection.y, detection.z, detection.length, detection.width);
            // }

            SendController::Ptr controllerMeta;
            if (ptrFrameBuf->getMeta(controllerMeta) == hva::hvaSuccess) {
                if (("Lidar" == controllerMeta->controlType || "All" == controllerMeta->controlType) && (0 < controllerMeta->capacity)) {
                    std::unique_lock<std::mutex> lock(controllerMeta->mtx);
                    (controllerMeta->count)--;
                    if (controllerMeta->count % controllerMeta->stride == 0) {
                        (controllerMeta->notFull).notify_all();
                    }
                    lock.unlock();
                }
            }

            hva::hvaVideoFrameWithMetaROIBuf_t::Ptr hvabuf =
                hva::hvaVideoFrameWithMetaROIBuf_t::make_buffer<std::vector<pointpillars::ObjectDetection>>(objectDetections, sizeof(objectDetections));

            CalibField_t calibContent;
            if (ptrFrameBuf->getMeta(calibContent) == hva::hvaSuccess) {
                hvabuf->setMeta(calibContent);
                HVA_DEBUG("Radar signal processing node copied calibContent to next buffer");
            }
            else {
                // previous node not ever put this type of meta into hvabuf
                HVA_ERROR("Previous node not ever put this type of TimeStamp_t into hvabuf!");
            }

            currentTime = std::chrono::high_resolution_clock::now();
            lidarTimeMeta.endTime = currentTime;

            hvabuf->setMeta(lidarTimeMeta);
            hvabuf->frameId = blob->frameId;
            hvabuf->tagAs(tag);

            auto lidarBlob = hva::hvaBlob_t::make_blob();

            lidarBlob->frameId = blob->frameId;
            lidarBlob->push(hvabuf);

            HVA_DEBUG("Lidar signal processing node sending blob with frameid %u and streamid %u, tag %d", lidarBlob->frameId, lidarBlob->streamId,
                      hvabuf->getTag());
            m_ctx.sendOutput(lidarBlob, 0, std::chrono::milliseconds(0));
            std::shared_ptr<hva::timeStampInfo> LidarSignalProcessingOut = std::make_shared<hva::timeStampInfo>(blob->frameId, "LidarSignalProcessingOut");
            m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &LidarSignalProcessingOut);
            HVA_DEBUG("Lidar signal processing node completed sent blob with frameid %u and streamid %u", lidarBlob->frameId, lidarBlob->streamId);
        }
        else {
            SendController::Ptr controllerMeta;
            if (ptrFrameBuf->getMeta(controllerMeta) == hva::hvaSuccess) {
                if (("Lidar" == controllerMeta->controlType || "All" == controllerMeta->controlType) && (0 < controllerMeta->capacity)) {
                    std::unique_lock<std::mutex> lock(controllerMeta->mtx);
                    (controllerMeta->count)--;
                    if (controllerMeta->count % controllerMeta->stride == 0) {
                        (controllerMeta->notFull).notify_all();
                    }
                    lock.unlock();
                }
            }

            std::vector<pointpillars::ObjectDetection> objectDetections;
            // LidarOutputs output;
            hva::hvaVideoFrameWithMetaROIBuf_t::Ptr hvabuf =
                hva::hvaVideoFrameWithMetaROIBuf_t::make_buffer<std::vector<pointpillars::ObjectDetection>>(objectDetections, 0);

            CalibField_t calibContent;
            if (ptrFrameBuf->getMeta(calibContent) == hva::hvaSuccess) {
                hvabuf->setMeta(calibContent);
                HVA_DEBUG("Radar signal processing node copied calibContent to next buffer");
            }
            else {
                // previous node not ever put this type of meta into hvabuf
                HVA_ERROR("Previous node not ever put this type of CalibField_t into hvabuf!");
            }

            currentTime = std::chrono::high_resolution_clock::now();
            lidarTimeMeta.endTime = currentTime;
            hvabuf->setMeta(lidarTimeMeta);
            HVA_DEBUG("Lidar signal processing node copied time_meta to next buffer");

            hvabuf->frameId = blob->frameId;
            hvabuf->tagAs(tag);
            hvabuf->drop = true;
            auto lidarBlob = hva::hvaBlob_t::make_blob();

            lidarBlob->frameId = blob->frameId;
            lidarBlob->push(hvabuf);

            HVA_DEBUG("Lidar signal processing node sending blob with frameid %u and streamid %u, tag %d, drop is true", lidarBlob->frameId,
                      lidarBlob->streamId, hvabuf->getTag());
            m_ctx.sendOutput(lidarBlob, 0, std::chrono::milliseconds(0));
            std::shared_ptr<hva::timeStampInfo> LidarSignalProcessingOut = std::make_shared<hva::timeStampInfo>(blob->frameId, "LidarSignalProcessingOut");
            m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &LidarSignalProcessingOut);
            HVA_DEBUG("Lidar signal processing node sent blob with frameid %u and streamid %u", lidarBlob->frameId, lidarBlob->streamId);
        }
    }
}

void LidarSignalProcessingNodeWorker::Impl::init() {}

hva::hvaStatus_t LidarSignalProcessingNodeWorker::Impl::rearm()
{
    return hva::hvaSuccess;
}
hva::hvaStatus_t LidarSignalProcessingNodeWorker::Impl::reset()
{
    return hva::hvaSuccess;
}

LidarSignalProcessingNodeWorker::LidarSignalProcessingNodeWorker(hva::hvaNode_t *parentNode,
                                                                 float scoreThreshold,
                                                                 float nmsThreshold,
                                                                 std::string device,
                                                                 const pointpillars::PointPillarsConfig &lidarConfig)
    : hva::hvaNodeWorker_t(parentNode), m_impl(new Impl(*this, scoreThreshold, nmsThreshold, device, lidarConfig))
{
}

LidarSignalProcessingNodeWorker::~LidarSignalProcessingNodeWorker() {}

void LidarSignalProcessingNodeWorker::process(std::size_t batchIdx)
{
    m_impl->process(batchIdx);
}

void LidarSignalProcessingNodeWorker::init()
{
    m_impl->init();
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(LidarSignalProcessingNode, LidarSignalProcessingNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce
