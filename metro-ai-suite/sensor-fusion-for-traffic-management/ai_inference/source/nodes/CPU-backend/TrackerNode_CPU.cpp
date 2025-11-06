/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2023 Intel Corporation.
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

#include <inc/util/hvaConfigStringParser.hpp>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>

#include "nodes/CPU-backend/TrackerNode_CPU.hpp"

namespace hce {

namespace ai {

namespace inference {


class _TrackerResultCollector {
  public:
    using Ptr = std::shared_ptr<_TrackerResultCollector>;

    _TrackerResultCollector(hva::hvaVideoFrameWithROIBuf_t::Ptr frameBuf, std::function<void(void)> fct) : m_frameBuf(frameBuf), m_fct(fct){};

    ~_TrackerResultCollector()
    {
        m_fct();
        HVA_DEBUG("TrackerResultCollector destructed");
    };
    bool setResult(const vas::ot::TrackResultContainer &track_in)
    {
        // process single tracklet
        TrackingStatus trackingStatus = (TrackingStatus)track_in.status;

        if (trackingStatus == TrackingStatus::LOST) {
            // to-do: to be decided: whether to save lost-status tracklet or not.
            // default: not to save

            if (m_applyLostROI) {
                applyTrackedROI(track_in);
            }
        }
        else {
            int matched_roi_idx = track_in.obj_index;
            if (matched_roi_idx < 0) {
                // no matching object
                return true;
            }
            else if (matched_roi_idx >= m_frameBuf->rois.size()) {
                HVA_ERROR("TrackerResultCollectors receives an invalid tracklet matching roi index: %d", matched_roi_idx);
                return false;
            }
            int hvaroi_idx = track_in.obj_index;

            if (hvaroi_idx > m_frameBuf->rois.size() - m_tracked) {
                HVA_ERROR("TrackerResultCollectors receives an invalid matched object index which is larger than the frame buf holds");
                return false;
            }

            //
            // update TrackInfo for detected rois
            //
            m_frameBuf->rois[hvaroi_idx].trackingId = track_in.track_id;
            // to-do: global tracking status need to be defined in hva_pipeline
            m_frameBuf->rois[hvaroi_idx].trackingStatus = (unsigned)trackingStatus;
        }
        return true;
    }

  private:
    hva::hvaVideoFrameWithROIBuf_t::Ptr m_frameBuf;
    std::function<void(void)> m_fct;
    int m_tracked = 0;
    bool m_applyLostROI = false;

    void applyTrackedROI(const vas::ot::TrackResultContainer &track_in)
    {
        hva::hvaROI_t vecObject;

        cv::Rect2f tracked_roi = track_in.obj_predicted;

        // extract lost roi info, save into m_frameBuf->rois
        vecObject.x = tracked_roi.x;
        vecObject.y = tracked_roi.y;
        vecObject.width = tracked_roi.width;
        vecObject.height = tracked_roi.height;

        vecObject.labelIdDetection = track_in.obj_label;
        vecObject.confidenceDetection = track_in.obj_confidence;
        // TODO: assign label for the predicted lost obj
        vecObject.labelDetection = track_in.obj_label;

        vecObject.trackingId = track_in.track_id;
        vecObject.trackingStatus = (unsigned)track_in.status;

        m_frameBuf->rois.push_back(vecObject);
        m_tracked++;

        HVA_DEBUG("TrackerResultCollectors insert tracked roi: x = %d, y = %d, w = %d, h = %d", vecObject.x, vecObject.y, vecObject.width, vecObject.height);
    };
};


class TrackerNode_CPU::Impl {
  public:
    Impl(TrackerNode_CPU &ctx);

    ~Impl();

    /**
     * @brief Parse params, called by hva framework right after node instantiate.
     * @param config Configure string required by this node.
     */
    hva::hvaStatus_t configureByString(const std::string &config);

    hva::hvaStatus_t validateConfiguration() const;

    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(TrackerNode_CPU *parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

  private:
    TrackerNode_CPU &m_ctx;

    hva::hvaConfigStringParser_t m_configParser;

    vas::ot::Tracker::InitParameters m_trackerParam;
};

TrackerNode_CPU::Impl::Impl(TrackerNode_CPU &ctx) : m_ctx(ctx)
{
    m_configParser.reset();
}

TrackerNode_CPU::Impl::~Impl() {}


/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 */
hva::hvaStatus_t TrackerNode_CPU::Impl::configureByString(const std::string &config)
{
    if (config.empty()) {
        return hva::hvaFailure;
    }

    if (!m_configParser.parse(config)) {
        HVA_ERROR("Illegal parse string!");
        return hva::hvaFailure;
    }

    m_trackerParam.max_num_objects = vas::ot::kDefaultMaxNumObjects;
    m_trackerParam.format = hce::ai::inference::ColorFormat::BGR;
    m_trackerParam.tracking_per_class = true;

    std::string tracker_type = "zero_term_imageless";
    m_configParser.getVal<std::string>("TrackerType", tracker_type);
    if (tracker_type == "zero_term_imageless") {
        m_trackerParam.tracking_type = vas::ot::TrackingAlgoType::ZERO_TERM_IMAGELESS;
    }
    else if (tracker_type == "zero_term_color_histogram") {
        m_trackerParam.tracking_type = vas::ot::TrackingAlgoType::ZERO_TERM_COLOR_HISTOGRAM;
    }
    else if (tracker_type == "short_term_imageless") {
        m_trackerParam.tracking_type = vas::ot::TrackingAlgoType::SHORT_TERM_IMAGELESS;
    }
    else {
        HVA_DEBUG("Tracker node receive invalid tracker type from configuration: %s, "
                  "support types: [zero_term_imageless, zero_term_color_histogram, "
                  "short_term_imageless]",
                  tracker_type);
        return hva::hvaFailure;
    }

    // after all configures being parsed, this node should be trainsitted to `configured`
    m_ctx.transitStateTo(hva::hvaState_t::configured);

    return hva::hvaSuccess;
}

hva::hvaStatus_t TrackerNode_CPU::Impl::prepare()
{
    // check streaming strategy: frames will be fetched in order
    auto configBatch = m_ctx.getBatchingConfig();
    if (configBatch.batchingPolicy != (unsigned)hva::hvaBatchingConfig_t::BatchingPolicy::BatchingWithStream) {
        if (m_ctx.getTotalThreadNum() == 1) {
            // set default parameters
            // configure streaming strategy
            configBatch.batchingPolicy = (unsigned)hva::hvaBatchingConfig_t::BatchingPolicy::BatchingWithStream;
            configBatch.streamNum = 1;
            configBatch.threadNumPerBatch = 1;
            configBatch.batchSize = 1;
            m_ctx.configBatch(configBatch);
            HVA_DEBUG("Tracker node change batching policy to BatchingPolicy::BatchingWithStream");
        }
        else {
            HVA_ERROR("Tracker node should use batching policy: BatchingPolicy::BatchingWithStream");
            return hva::hvaFailure;
        }
    }

    return hva::hvaSuccess;
}

hva::hvaStatus_t TrackerNode_CPU::Impl::validateConfiguration() const
{
    // to-do: tracker

    return hva::hvaSuccess;
}

std::shared_ptr<hva::hvaNodeWorker_t> TrackerNode_CPU::Impl::createNodeWorker(TrackerNode_CPU *parent) const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>{new TrackerNodeWorker_CPU{parent, m_trackerParam}};
}

hva::hvaStatus_t TrackerNode_CPU::Impl::rearm()
{
    // to-do:
    return hva::hvaSuccess;
}

hva::hvaStatus_t TrackerNode_CPU::Impl::reset()
{
    // to-do:
    return hva::hvaSuccess;
}

TrackerNode_CPU::TrackerNode_CPU(std::size_t totalThreadNum) : hva::hvaNode_t(1, 1, totalThreadNum), m_impl(new Impl(*this)) {}

TrackerNode_CPU::~TrackerNode_CPU() {}

hva::hvaStatus_t TrackerNode_CPU::configureByString(const std::string &config)
{
    return m_impl->configureByString(config);
}

hva::hvaStatus_t TrackerNode_CPU::validateConfiguration() const
{
    return m_impl->validateConfiguration();
}

std::shared_ptr<hva::hvaNodeWorker_t> TrackerNode_CPU::createNodeWorker() const
{
    return m_impl->createNodeWorker(const_cast<TrackerNode_CPU *>(this));
}

hva::hvaStatus_t TrackerNode_CPU::rearm()
{
    return m_impl->rearm();
}

hva::hvaStatus_t TrackerNode_CPU::reset()
{
    return m_impl->reset();
}

hva::hvaStatus_t TrackerNode_CPU::prepare()
{
    return m_impl->prepare();
}

class TrackerNodeWorker_CPU::Impl {
  public:
    Impl(TrackerNodeWorker_CPU &ctx, const vas::ot::Tracker::InitParameters &tracker_param);

    ~Impl();

    void process(std::size_t batchIdx);

    void init();

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

  private:
    TrackerNodeWorker_CPU &m_ctx;

    float m_durationAve{0.0f};
    std::atomic<int32_t> m_cntProcessEnd{0};

    bool m_imagelessFlag;
    float m_delta_t = 0.033f;  // kalman_filter param
    vas::ot::Tracker::InitParameters m_trackerParam;
    std::unique_ptr<vas::ot::Tracker> m_motTracker;
    std::vector<std::shared_ptr<vas::ot::Tracklet>> m_producedTracklets;
    int m_workStreamId;

    cv::Mat m_dummyMat;
    void prepareDummyCvMat(size_t height, size_t width, hce::ai::inference::ColorFormat color);
};

TrackerNodeWorker_CPU::Impl::Impl(TrackerNodeWorker_CPU &ctx, const vas::ot::Tracker::InitParameters &tracker_param)
    : m_ctx(ctx), m_trackerParam(tracker_param), m_workStreamId(-1)
{
}

TrackerNodeWorker_CPU::Impl::~Impl() {}


void TrackerNodeWorker_CPU::Impl::prepareDummyCvMat(size_t height, size_t width, hce::ai::inference::ColorFormat format)
{
    cv::Size cv_size(width, height);
    if (format == hce::ai::inference::ColorFormat::NV12 || format == hce::ai::inference::ColorFormat::I420)
        cv_size.height = cv_size.height * 3 / 2;
    m_dummyMat = cv::Mat(cv_size, CV_8UC3);
}

/**
 * @brief Called by hva framework for each video frame, Run inference and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void TrackerNodeWorker_CPU::Impl::process(std::size_t batchIdx)
{
    // get input blob from port 0
    std::vector<hva::hvaBlob_t::Ptr> vecBlobInput = m_ctx.getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});

    // input blob is not empty
    for (const auto &blob : vecBlobInput) {
        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrVideoBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(blob->get(0));
        HVA_ASSERT(ptrVideoBuf);
        std::shared_ptr<hva::timeStampInfo> MediaTrackerIn = std::make_shared<hva::timeStampInfo>(blob->frameId, "MediaTrackerIn");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &MediaTrackerIn);

        HVA_DEBUG("Tracker node %d on frameId %u and streamid %u with tag %d", batchIdx, blob->frameId, blob->streamId, ptrVideoBuf->getTag());

        auto procStart = std::chrono::steady_clock::now();
        m_ctx.getLatencyMonitor().startRecording(blob->frameId, "tracking");

        int streamId = (int)blob->streamId;

        if (m_workStreamId >= 0 && streamId != m_workStreamId) {
            HVA_ERROR("Tracker worker should work on streamId: %d, but received "
                      "data from invalid streamId: %d!",
                      m_workStreamId, streamId);
            // send output
            ptrVideoBuf->drop = true;
            ptrVideoBuf->rois.clear();
            HVA_DEBUG("Tracker sending blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
            m_ctx.sendOutput(blob, 0, std::chrono::milliseconds(0));
            HVA_DEBUG("Tracker completed sent blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
            continue;
        }
        else {
            // the first coming stream decides the workStreamId for this worker
            m_workStreamId = streamId;
        }

        //
        // finalize function
        // register sendOutput in _TrackerResultCollector deConsctruct
        // ~_TrackerResultCollector() be called after all rois are processed.
        //
        _TrackerResultCollector::Ptr collector = std::make_shared<_TrackerResultCollector>(ptrVideoBuf, [=]() {
            hva::hvaVideoFrameWithROIBuf_t::Ptr temp = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(blob->get(0));
            unsigned roisize = temp->rois.size();
            HVA_DEBUG("Tracker sending buf with roi size %d", roisize);
            if (roisize != 0) {
                for (const auto &item : temp->rois) {
                    HVA_DEBUG("[%d, %d, %d, %d]", item.x, item.y, item.width, item.height);
                }
            }

            HceDatabaseMeta meta;
            if (blob->get(0)->getMeta(meta) == hva::hvaSuccess) {
                HVA_DEBUG("Tracker node sends meta to next buffer, mediauri: %s", meta.mediaUri.c_str());
            }

            // process done
            auto procEnd = std::chrono::steady_clock::now();
            auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(procEnd - procStart).count();
            m_ctx.getLatencyMonitor().stopRecording(blob->frameId, "tracking");

            // calculate duration
            m_durationAve = (m_durationAve * (int)m_cntProcessEnd + duration) / ((int)m_cntProcessEnd + 1);
            m_cntProcessEnd++;
            HVA_DEBUG("Tracker node average duration is %ld ms for %d rois, at processing cnt: %d", (int)m_durationAve, roisize, (int)m_cntProcessEnd);

            // send output to the subsequent nodes
            HVA_DEBUG("Tracker node sending blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
            m_ctx.sendOutput(blob, 0, std::chrono::milliseconds(0));

            // release `depleting` status in hva pipeline
            m_ctx.getParentPtr()->releaseDepleting();
            HVA_DEBUG("Tracker node completed sent blob with frameid %u and streamid %u", blob->frameId, blob->streamId);

            if (ptrVideoBuf->getTag() == hvaBlobBufferTag::END_OF_REQUEST) {
                // receive end of stream, motTracker should be reset
                reset();
                HVA_DEBUG("Tracker node receiving the end of stream, reset motTracker contexts with frameid %u and streamid %u", blob->frameId, blob->streamId);
            }
        });

        // coming empty buf
        if (ptrVideoBuf->drop) {
            ptrVideoBuf->rois.clear();
            SendController::Ptr controllerMeta;
            if (blob->get(0)->getMeta(controllerMeta) == hva::hvaSuccess) {
                if ((m_workStreamId >= 0) && (streamId == m_workStreamId) && ("Video" == controllerMeta->controlType || "All" == controllerMeta->controlType) &&
                    (0 < controllerMeta->capacity)) {
                    std::unique_lock<std::mutex> lock(controllerMeta->mtx);
                    (controllerMeta->count)--;
                    if (controllerMeta->count % controllerMeta->stride == 0) {
                        (controllerMeta->notFull).notify_all();
                    }
                    lock.unlock();
                }
            }

            VideoTimeStamp_t videoTimeMeta;
            if (blob->get(0)->getMeta(videoTimeMeta) == hva::hvaSuccess) {
                std::chrono::time_point<std::chrono::high_resolution_clock> currentTime = std::chrono::high_resolution_clock::now();
                videoTimeMeta.endTime = currentTime;
                blob->get(0)->setMeta(videoTimeMeta);
            }

            HVA_DEBUG("Tracker node dropped a frame on frameid %u and streamid %u", blob->frameId, blob->streamId);
            // sendOutput called at ~_TrackerResultCollector()
            return;
        }

        // start processing

        // inherit meta data from previous input field
        HceDatabaseMeta inputMeta;
        if (blob->get(0)->getMeta(inputMeta) != hva::hvaSuccess) {
            HVA_DEBUG("Detection node %d on frameId %d read meta data error!", batchIdx, blob->frameId);
        }

        // no rois detected this frame
        if (ptrVideoBuf->rois.size() == 0) {
            // if none rois are received, and none tracklets exist, then no need to do tracking here.
            if (m_producedTracklets.size() == 0) {
                SendController::Ptr controllerMeta;
                if (blob->get(0)->getMeta(controllerMeta) == hva::hvaSuccess) {
                    if ((m_workStreamId >= 0) && (streamId == m_workStreamId) &&
                        ("Video" == controllerMeta->controlType || "All" == controllerMeta->controlType) && (0 < controllerMeta->capacity)) {
                        std::unique_lock<std::mutex> lock(controllerMeta->mtx);
                        (controllerMeta->count)--;
                        if (controllerMeta->count % controllerMeta->stride == 0) {
                            (controllerMeta->notFull).notify_all();
                        }
                        lock.unlock();
                    }
                }

                VideoTimeStamp_t videoTimeMeta;
                if (blob->get(0)->getMeta(videoTimeMeta) == hva::hvaSuccess) {
                    std::chrono::time_point<std::chrono::high_resolution_clock> currentTime = std::chrono::high_resolution_clock::now();
                    videoTimeMeta.endTime = currentTime;
                    blob->get(0)->setMeta(videoTimeMeta);
                }

                HVA_DEBUG("No ROI is provided on frameid %u at TrackerNode. And no tracklets exist, skipping...", blob->frameId);
                // sendOutput called at ~_TrackerResultCollector()
                return;
            }
            else {
                HVA_DEBUG("No ROI is provided on frameid %u at TrackerNode. But still tracking...", blob->frameId);
            }
        }
        //
        //  ptrVideoBuf->frameId： the relative frame number in one video.
        //  blob->frameId： global frame number in one request, can contain multiple videos.
        //
        int video_frame_index = ptrVideoBuf->frameId;

        // mark `depleting` status in hva pipeline
        m_ctx.getParentPtr()->holdDepleting();

        // convert hvaROI to vas::ot::Detection
        std::vector<vas::ot::Detection> detections;
        int32_t index = 0;
        for (const auto &object : ptrVideoBuf->rois) {
            vas::ot::Detection detection;

            detection.class_label = object.labelIdDetection;
            detection.class_label_name = object.labelDetection;
            detection.confidence = object.confidenceDetection;
            cv::Rect obj_rect(object.x, object.y, object.width, object.height);
            detection.rect = static_cast<cv::Rect2f>(obj_rect);
            detection.index = index;  // identity index in hvaROIs

            detections.emplace_back(detection);
            index++;
        }

        try {
            int input_height = ptrVideoBuf->height;
            int input_width = ptrVideoBuf->width;
            HVA_DEBUG("Tracker node receiving buffer with size: [%d, %d] on frameid %u and streamid %u", input_height, input_width, blob->frameId,
                      blob->streamId);
            /**
             * play tracking
             */
            if (m_imagelessFlag) {
                // For imageless algorithms image data is not important
                // So in this case dummy (empty) cv::Mat is passed to avoid redundant buffer map/unmap operations
                if (m_dummyMat.empty()) {
                    prepareDummyCvMat(input_height, input_width, hce::ai::inference::ColorFormat::BGR);
                }
                m_motTracker->TrackObjects(m_dummyMat, detections, &m_producedTracklets, m_delta_t);
            }
            else {
                // read image data from buffer
                cv::Mat decodedImage;
                const uint8_t *pBuffer;

                if (inputMeta.bufType == HceDataMetaBufType::BUFTYPE_UINT8) {
                    // read image data from buffer
                    pBuffer = ptrVideoBuf->get<uint8_t *>();
                    if (pBuffer == NULL) {
                        HVA_DEBUG("Tracker node receiving an empty buffer on frameid %u and streamid %u, skipping", blob->frameId, blob->streamId);
                        ptrVideoBuf->rois.clear();
                        // sendOutput called at ~_TrackerResultCollector()
                        return;
                    }
                    decodedImage = cv::Mat(input_height, input_width, CV_8UC3, (uint8_t *)pBuffer);
                    m_motTracker->SetImageColorFormat(hce::ai::inference::ColorFormat::BGR);
                    m_motTracker->TrackObjects(decodedImage, detections, &m_producedTracklets, m_delta_t);
                }
                else if (inputMeta.bufType == HceDataMetaBufType::BUFTYPE_MFX_FRAME) {
                    // #ifdef ENABLE_VAAPI
                    //                     HVA_WARNING("Buffer type of mfxFrame is received, will do mapping. This may slow down pipeline performance");
                    //                     std::string dataStr;
                    //                     mfxFrameSurface1* surfPtr = ptrVideoBuf->get<mfxFrameSurface1*>();
                    //                     if (surfPtr == NULL) {
                    //                         HVA_DEBUG("Tracker node receiving an empty buffer on frameid %u and streamid %u, skipping", blob->frameId,
                    //                         blob->streamId); ptrVideoBuf->rois.clear();
                    //                         // sendOutput called at ~_TrackerResultCollector()
                    //                         return;
                    //                     }
                    //                     surfPtr->FrameInterface->AddRef(surfPtr);
                    //                     WriteRawFrame_InternalMem(surfPtr, dataStr);
                    //                     pBuffer = (uint8_t*)dataStr.c_str();
                    //                     input_height *= 1.5;
                    //                     decodedImage = cv::Mat(input_height, input_width, CV_8UC1, (uint8_t*)pBuffer);
                    //                     m_motTracker->SetImageColorFormat(hce::ai::inference::ColorFormat::NV12);
                    //                     m_motTracker->TrackObjects(decodedImage, detections, &m_producedTracklets, m_delta_t);
                    // #else
                    //                     HVA_ERROR("Buffer type of mfxFrame is received but GPU support is not enabled");
                    //                     continue;
                    // #endif
                }
                else {
                    HVA_ERROR("Unsupported buffer type");
                    continue;
                }
            }
            // collect tracking results for current frame
            std::vector<vas::ot::TrackResultContainer> current_result = m_motTracker->FormatTrackResult();
            HVA_DEBUG("+ Number: Tracking objects (%d)", static_cast<int32_t>(current_result.size()));
            for (auto &trk_in : current_result) {
                if (!collector->setResult(trk_in)) {
                    HVA_ERROR("Submiting tracker node results error on frameid %u and streamid %u, at tracklet: %d", blob->frameId, blob->streamId,
                              trk_in.track_id);
                }
            }
            SendController::Ptr controllerMeta;
            if (blob->get(0)->getMeta(controllerMeta) == hva::hvaSuccess) {
                if ((m_workStreamId >= 0) && (streamId == m_workStreamId) && ("Video" == controllerMeta->controlType || "All" == controllerMeta->controlType) &&
                    (0 < controllerMeta->capacity)) {
                    std::unique_lock<std::mutex> lock(controllerMeta->mtx);
                    (controllerMeta->count)--;
                    if (controllerMeta->count % controllerMeta->stride == 0) {
                        (controllerMeta->notFull).notify_all();
                    }
                    lock.unlock();
                }
            }

            VideoTimeStamp_t videoTimeMeta;
            if (blob->get(0)->getMeta(videoTimeMeta) == hva::hvaSuccess) {
                std::chrono::time_point<std::chrono::high_resolution_clock> currentTime = std::chrono::high_resolution_clock::now();
                videoTimeMeta.endTime = currentTime;
                blob->get(0)->setMeta(videoTimeMeta);
            }

            HVA_DEBUG("Submiting tracker node on frameid %u with rois: %d", blob->frameId, ptrVideoBuf->rois.size());
        }
        catch (std::exception &e) {
            std::cout << e.what() << std::endl;
            HVA_DEBUG("Tracker node exception error with frameid %u and streamid %u", blob->frameId, blob->streamId);

            // catch error during inference, clear context
            ptrVideoBuf->rois.clear();
            // sendOutput called at ~_TrackerResultCollector()
            return;
        }
        catch (...) {
            HVA_DEBUG("Tracker node exception error with frameid %u and streamid %u", blob->frameId, blob->streamId);

            // catch error during inference, clear context
            ptrVideoBuf->rois.clear();
            // sendOutput called at ~_TrackerResultCollector()
            return;
        }
        HVA_DEBUG("Tracker node loop end, frame id is %d, stream id is %d\n", blob->frameId, blob->streamId);
        std::shared_ptr<hva::timeStampInfo> MediaTrackerOut = std::make_shared<hva::timeStampInfo>(blob->frameId, "MediaTrackerOut");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &MediaTrackerOut);
    }
}

void TrackerNodeWorker_CPU::Impl::init()
{
    auto type = m_trackerParam.tracking_type;
    m_imagelessFlag = type == vas::ot::TrackingAlgoType::ZERO_TERM_IMAGELESS || type == vas::ot::TrackingAlgoType::SHORT_TERM_IMAGELESS;
    m_motTracker.reset(vas::ot::Tracker::CreateInstance(m_trackerParam));
    m_producedTracklets.clear();
    HVA_DEBUG("Tracker node init motTracker");
}

hva::hvaStatus_t TrackerNodeWorker_CPU::Impl::rearm()
{
    // reset all trackers when new video coming
    m_motTracker->Reset();
    m_producedTracklets.clear();
    HVA_DEBUG("Tracker node reset motTracker");

    return hva::hvaSuccess;
}

hva::hvaStatus_t TrackerNodeWorker_CPU::Impl::reset()
{
    // reset all trackers when new video coming
    m_motTracker->Reset();
    m_producedTracklets.clear();
    HVA_DEBUG("Tracker node reset motTracker");

    return hva::hvaSuccess;
}

TrackerNodeWorker_CPU::TrackerNodeWorker_CPU(hva::hvaNode_t *parentNode, const vas::ot::Tracker::InitParameters &tracker_param)
    : hva::hvaNodeWorker_t(parentNode), m_impl(new Impl(*this, tracker_param))
{
}

TrackerNodeWorker_CPU::~TrackerNodeWorker_CPU() {}

void TrackerNodeWorker_CPU::process(std::size_t batchIdx)
{
    m_impl->process(batchIdx);
}

void TrackerNodeWorker_CPU::init()
{
    m_impl->init();
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(TrackerNode_CPU, TrackerNode_CPU(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce
