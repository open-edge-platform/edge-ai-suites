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

#include "nodes/CPU-backend/ObjectSelectNode.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce{

namespace ai{

namespace inference{


class _ObjectSelectResultCollector{
public:
    using Ptr = std::shared_ptr<_ObjectSelectResultCollector>;

    /// @brief describe object quality assessment results
    struct _CandidateROI_t {
        float collect_index;
        float roi_index;
    };

    _ObjectSelectResultCollector(std::function<void(void)> fct)
            : m_fct(fct), m_tag(0u), m_roiCnt(0) {};

    ~_ObjectSelectResultCollector(){
        m_fct();
        HVA_DEBUG("_ObjectSelectResultCollector destructed");
    };

    /**
     * @brief collect all comming blobs during one selection interval
     * 
     */
    void setResult(const hva::hvaBlob_t::Ptr blob) {

        // read input buf from current blob
        hva::hvaVideoFrameWithROIBuf_t::Ptr frameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(blob->get(0));
        HVA_ASSERT(frameBuf);

        // read meta data from current blob
        HceDatabaseMeta meta;
        blob->get(0)->getMeta(meta);
        HceDatabaseMeta::Ptr frameMeta = std::make_shared<HceDatabaseMeta>(meta);
        HVA_ASSERT(frameMeta);

        if (frameBuf->getTag() == hvaBlobBufferTag::END_OF_REQUEST) {
            // the last frame is coming
            m_tag = frameBuf->getTag();
            HVA_DEBUG("Receive tag %s on frame %d", buffertag_to_string(m_tag).c_str(), blob->frameId);
        }
        m_roiCnt += frameBuf->rois.size();

        m_collectedBlob.push_back(blob);
        m_collectedFrameBuf.push_back(frameBuf);
        m_collectedFrameMeta.push_back(frameMeta);
    }

    /**
     * @brief collected frames count
     * 
     */
    int getFrameCnt() {
        return m_collectedFrameBuf.size();
    }

    /**
     * @brief collected rois count
     * 
     */
    int getROICnt() {
        return m_roiCnt;
    }

    /**
     * @brief add ignore flag for each roi according to whether being selected or not
     * @param topK, select topK rois. If topK == 0, then it's used to initialize all ignore flag to true
     * @param trackletAware, whether selection action is for each tracklet independently? True: yes, False: no
     * @return unsigned, actually selected count
     */
    unsigned runSelection(unsigned topK, bool trackletAware) {

        // for sanity
        if (m_collectedBlob.size() != m_collectedFrameBuf.size() ||
            m_collectedFrameBuf.size() != m_collectedFrameMeta.size()) {
            HVA_ERROR(
                "_ObjectSelectResultCollector receiving invalid size of "
                "frame-list and meta-data-list, %d vs. %d",
                m_collectedFrameBuf.size(), m_collectedFrameMeta.size());
            throw std::runtime_error("Error during selection.");
        }

        // 
        // > if trackletAware is true:
        //      gather rois for per track_id: {track_id, roi_info}
        // > else
        //      gather all rois together: {0, roi_info}
        std::unordered_map<unsigned, std::vector<_CandidateROI_t>> allCandidates;
        std::unordered_map<unsigned, std::vector<_CandidateROI_t>> selectedCandidates;

        gatherCandidates(allCandidates, trackletAware);
        
        size_t selectedCnt = 0;
        std::unordered_map<unsigned, std::vector<_CandidateROI_t>>::iterator iter_;
        for (iter_ = allCandidates.begin(); iter_ != allCandidates.end(); iter_ ++) {

            // 
            // select topK rois with high quality score
            // 
        
            unsigned trackingId = iter_->first;
            std::vector<_CandidateROI_t> candidateROIs = iter_->second;
            std::vector<size_t> vecQualityScores;

            for (auto &roiInfo : candidateROIs) {
                size_t cid = roiInfo.collect_index;
                size_t rid = roiInfo.roi_index;
                float score = m_collectedFrameMeta[cid]->qualityResult[rid];
                vecQualityScores.push_back(score);
            }

            // 
            // We don't generate new blobs for selected objects, we just modify the `ignore` flag for each roi.
            // and let the downstream nodes to decide their actions. 
            // 
            std::vector<size_t> index = argsort(vecQualityScores);
            size_t ii;
            for (ii = 0; ii < topK && ii < index.size(); ii ++) {
                _CandidateROI_t _cur = candidateROIs[index[ii]];
                selectedCandidates[trackingId].push_back(_cur);
                m_collectedFrameMeta[_cur.collect_index]->ignoreFlags[_cur.roi_index] = false;
            }
            selectedCnt += ii;
            for (; ii < index.size(); ii ++) {
                _CandidateROI_t _cur = candidateROIs[index[ii]];
                m_collectedFrameMeta[_cur.collect_index]->ignoreFlags[_cur.roi_index] = true;
            }
        }

        // traverse all collected blobs, refresh the selection flag
        for (size_t cid = 0; cid < m_collectedFrameBuf.size(); cid ++) {

            auto curMeta = m_collectedFrameMeta[cid];

            // refresh the selection flag in `meta`
            m_collectedBlob[cid]->get(0)->setMeta(*curMeta);
        }

        return selectedCnt;
    }

    /**
     * @brief get collected blobs
     */
    std::vector<hva::hvaBlob_t::Ptr> getCollectedBlobs() {
        return m_collectedBlob;
    }

private:
    std::function<void(void)> m_fct;
    
    std::vector<hva::hvaBlob_t::Ptr> m_collectedBlob;
    std::vector<hva::hvaVideoFrameWithROIBuf_t::Ptr> m_collectedFrameBuf;
    std::vector<HceDatabaseMeta::Ptr> m_collectedFrameMeta;

    // hvabuf tag, 1: end of request
    // if m_tag == 1: this collection round is the final one
    unsigned m_tag;

    int m_roiCnt;       // collected rois

    /**
     * @brief sort vector but only return corresponding indices
     * 
     * @tparam T 
     * @param array 
     * @return indices for the sorted results from larger to small
     */
    template<typename T> std::vector<size_t> argsort(const std::vector<T>& array)
    { 
        const int array_len(array.size());
        std::vector<size_t> array_index(array_len, 0);
        for (int i = 0; i < array_len; ++i)
            array_index[i] = i;
        std::sort(array_index.begin(), array_index.end(),
            [&array](int pos1, int pos2) { return (array[pos1] > array[pos2]);});
        return array_index;
    }

    /**
     * @brief validate tracklet status
     *        > alive: TrackingStatus::TRACKED || TrackingStatus::NEW
     *        > ignore: TrackingStatus::LOST || TrackingStatus::DEAD
     * 
     * @param status 
     * @return true: alive tracked rois
     * @return false: ignore tracked rois
     */
    bool validTrackStatus(unsigned status) {
        
        if (status == (unsigned)TrackingStatus::TRACKED || 
            status == (unsigned)TrackingStatus::NEW) 
        {
            return true;
        }
        else {
            return false;
        }
    }

    /**
     * @brief gather candidates during this selection interval
     * > if trackletAware is false:
     *      just gather all rois together: {0, roi_info}
     *      for example:
     *          [input]
     *           frame_0: [trk_0, trk_1, trk_2]
     *           frame_1: [trk_0, trk_1]
     *           frame_2: [trk_0, trk_1, trk_3]
     *           frame_3: [trk_0, trk_3]
     *          [output]
     *           0: (frame_0, roi_info), (frame_1, roi_info), (frame2, roi_info), (frame_3, roi_info), ...
     *      
     * > else
     *      gather rois for per track_id: {track_id, roi_info}
     *      for example:
     *          [input]
     *           frame_0: [trk_0, trk_1, trk_2]
     *           frame_1: [trk_0, trk_1]
     *           frame_2: [trk_0, trk_1, trk_3]
     *           frame_3: [trk_0, trk_3]
     *          [output]
     *           0: (frame_0, roi_info), (frame_1, roi_info), (frame2, roi_info), (frame_3, roi_info)
     *           1: (frame_0, roi_info), (frame_1, roi_info), (frame2, roi_info)
     *           2: (frame_0, roi_info)
     *           3: (frame2, roi_info), (frame_3, roi_info)
     * @param candidates, {track_id, roi_info}, save the gathered candidates rois for each track-id
     */
    bool gatherCandidates(std::unordered_map<unsigned, std::vector<_CandidateROI_t>> &candidates, bool trackletAware) {

        // traverse all collected hva buffers
        for (size_t cid = 0; cid < m_collectedFrameBuf.size(); cid ++) {
            auto &buf = m_collectedFrameBuf[cid];
            std::vector<hva::hvaROI_t> rois = buf->rois;

            // collect all detected rois, grouped by tracking-id
            for (size_t rid = 0; rid < rois.size(); rid ++) {

                if (trackletAware) {
                    unsigned trackingId = rois[rid].trackingId;
                    unsigned status = rois[rid].trackingStatus;

                    //
                    //  > TrackingStatus::LOST should be ignored
                    //  > TrackingStatus::DEAD won't exit here
                    //
                    if(validTrackStatus(status)) {
                        _CandidateROI_t info;
                        info.collect_index = cid;
                        info.roi_index = rid;
                        candidates[trackingId].push_back(info);
                    }
                }
                else {
                    _CandidateROI_t info;
                    info.collect_index = cid;
                    info.roi_index = rid;
                    candidates[0].push_back(info);
                }

            }

        }
        return true;
    }

};

class ObjectSelectNode::Impl{
public:

    Impl(ObjectSelectNode& ctx);

    ~Impl();

    /**
    * @brief Parse params, called by hva framework right after node instantiate.
    * @param config Configure string required by this node.
    */
    hva::hvaStatus_t configureByString(const std::string& config);

    /**
    * @brief validate configuration
    * @return sucess status
    */
    hva::hvaStatus_t validateConfiguration() const;

    /**
    * @brief Constructs and returns a node worker instance: ObjectSelectNodeWorker .
    * @param void
    */
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(ObjectSelectNode* parent) const;

    /**
     * @brief hvaframework: rearm
     * @return sucess status
     */
    hva::hvaStatus_t rearm();

    /**
     * @brief hvaframework: reset
     * @return sucess status
     */
    hva::hvaStatus_t reset();

    /**
     * @brief hvaframework: prepare
     * @return sucess status
     */
    hva::hvaStatus_t prepare();

private:

    ObjectSelectNode& m_ctx;
    hva::hvaConfigStringParser_t m_configParser;

    // object selection parameters
    ObjectSelectParam_t m_selectParams;
};

ObjectSelectNode::Impl::Impl(ObjectSelectNode& ctx):m_ctx(ctx){
    m_configParser.reset();
}

ObjectSelectNode::Impl::~Impl(){

}

/**
* @brief Parse params, called by hva framework right after node instantiate.
* @param config Configure string required by this node.
* @return success status
*/
hva::hvaStatus_t ObjectSelectNode::Impl::configureByString(const std::string& config){
    if(config.empty()){
        return hva::hvaFailure;
    }

    if(!m_configParser.parse(config)){
        HVA_ERROR("Illegal parse string!");
        return hva::hvaFailure;
    }

    // selection interval
    int32_t frameInterval = 30;
    m_configParser.getVal<int32_t>("FrameInterval", frameInterval);
    m_selectParams.frameInterval = frameInterval;

    // selection count
    int32_t topK = 1;
    m_configParser.getVal<int32_t>("TopK", topK);
    m_selectParams.topK = topK;

    // whether topK apply to each tracklet or not?
    bool trackletAware = true;
    m_configParser.getVal<bool>("TrackletAware", trackletAware);
    m_selectParams.trackletAware = trackletAware;

    // selection strategy
    std::string strategy = "all_in_best_out";
    m_configParser.getVal<std::string>("Strategy", strategy);
    if (strategy == "all_in_best_out") {
        m_selectParams.strategy = ObjectSelectStrategy_t::ALL_IN_BEST_OUT;
    }
    else if (strategy == "first_in_first_out") {
        m_selectParams.strategy = ObjectSelectStrategy_t::FIRST_IN_FIRST_OUT;
    }
    else {
        HVA_ERROR("Unknown selection strategy received: %s, supported: [all_in_best_out, first_in_first_out]", strategy.c_str());
        return hva::hvaFailure;
    }

    // after all configures being parsed, this node should be trainsitted to `configured`
    m_ctx.transitStateTo(hva::hvaState_t::configured);

    return hva::hvaSuccess;
}

hva::hvaStatus_t ObjectSelectNode::Impl::prepare(){

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
            HVA_DEBUG("Object select node change batching policy to BatchingPolicy::BatchingWithStream");
        }
        else {
            HVA_ERROR("Object select node should use batching policy: BatchingPolicy::BatchingWithStream");
            return hva::hvaFailure;
        }
    }

    return hva::hvaSuccess;
}

hva::hvaStatus_t ObjectSelectNode::Impl::validateConfiguration() const{

    return hva::hvaSuccess;
}

std::shared_ptr<hva::hvaNodeWorker_t> ObjectSelectNode::Impl::createNodeWorker(ObjectSelectNode* parent) const{
    return std::shared_ptr<hva::hvaNodeWorker_t>{new ObjectSelectNodeWorker{parent, m_selectParams}};
}

hva::hvaStatus_t ObjectSelectNode::Impl::rearm(){

    return hva::hvaSuccess;
}

hva::hvaStatus_t ObjectSelectNode::Impl::reset(){

    return hva::hvaSuccess;
}

ObjectSelectNode::ObjectSelectNode(std::size_t totalThreadNum):hva::hvaNode_t(1, 1, totalThreadNum), m_impl(new Impl(*this)){

}

ObjectSelectNode::~ObjectSelectNode(){

}

hva::hvaStatus_t ObjectSelectNode::configureByString(const std::string& config){
    return m_impl->configureByString(config);
}

hva::hvaStatus_t ObjectSelectNode::validateConfiguration() const{
    return m_impl->validateConfiguration();
}

std::shared_ptr<hva::hvaNodeWorker_t> ObjectSelectNode::createNodeWorker() const{
    return m_impl->createNodeWorker(const_cast<ObjectSelectNode*>(this));
}

hva::hvaStatus_t ObjectSelectNode::rearm(){
    return m_impl->rearm();
}

hva::hvaStatus_t ObjectSelectNode::reset(){
    return m_impl->reset();
}

hva::hvaStatus_t ObjectSelectNode::prepare(){
    return m_impl->prepare();
}

class ObjectSelectNodeWorker::Impl{
public:

    Impl(ObjectSelectNodeWorker& ctx, const ObjectSelectParam_t& selectParams);

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

    ObjectSelectNodeWorker& m_ctx;

    float m_durationAve {0.0f};
    float m_collectDurationAve {0.0f};
    std::atomic<int32_t> m_cntProcessEnd{0};

    ObjectSelectParam_t m_selectParams;
    unsigned m_accumulatedSelectROIs;

    /**
     * @brief Accumulated selected rois count increased for every selection action, 
     *          should be re-init every selection inteval(i.e. m_selectParams.frameInterval)
     * @param count, new selected rois
     * @return Selected ROIs count
     */
    unsigned add_selected(unsigned count);
    
    /**
     * @brief get the selected rois count
     * @return Selected ROIs count
     */
    unsigned get_selected();
    
    /**
     * @brief reset the selected rois count
     * @return void
     */
    void reset_selected();

};

ObjectSelectNodeWorker::Impl::Impl(ObjectSelectNodeWorker& ctx, const ObjectSelectParam_t& selectParams):
        m_ctx(ctx), m_selectParams(selectParams), m_accumulatedSelectROIs(0) {
}

ObjectSelectNodeWorker::Impl::~Impl(){
    
}

/**
 * @brief Accumulated selected rois count increased for every selection action, 
 *          should be re-init every selection inteval(i.e. m_selectParams.frameInterval)
 * @param count, new selected rois
 * @return Selected ROIs count
 */
unsigned ObjectSelectNodeWorker::Impl::add_selected(unsigned count) { 
    m_accumulatedSelectROIs += count;
    return m_accumulatedSelectROIs;
}

/**
 * @brief get the selected rois cound
 * @return Selected ROIs count
 */
unsigned ObjectSelectNodeWorker::Impl::get_selected() {
    return m_accumulatedSelectROIs;
}

/**
 * @brief reset the selected rois count
 * @return void
 */
void ObjectSelectNodeWorker::Impl::reset_selected() {
    m_accumulatedSelectROIs = 0;
}

/**
 * @brief Called by hva framework for each video frame, Run inference and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void ObjectSelectNodeWorker::Impl::process(std::size_t batchIdx){

    // start collecting comming buffers
    auto collectStart = std::chrono::steady_clock::now();

    //
    // finalize function
    // register sendOutput in _ObjectSelectResultCollector deConsctruct
    // ~_ObjectSelectResultCollector() be called after all rois are processed.
    //
    _ObjectSelectResultCollector::Ptr collector = std::make_shared<_ObjectSelectResultCollector>([=](){
                
                // collection done
                auto collectEnd = std::chrono::steady_clock::now();

                // calculate global duration: collection + selection
                auto collectDuration = std::chrono::duration_cast<std::chrono::milliseconds>(collectEnd - collectStart).count();
                m_collectDurationAve = (m_collectDurationAve * (int)m_cntProcessEnd + collectDuration) / ((int)m_cntProcessEnd + 1);
                HVA_DEBUG("Object select node average collection duration is %ld ms, at processing cnt: %d", 
                            (int)m_collectDurationAve, (int)m_cntProcessEnd);
                m_cntProcessEnd ++;
                
                // release `depleting` status in hva pipeline
                m_ctx.getParentPtr()->releaseDepleting();
                HVA_DEBUG("Object select node completed sent all blobs");
    });

    bool flag = false;
    while (!flag) {  // keep reading blob data until frame_index meet the selection interval: `m_selectParams.frameInterval`
        // get input blob from port 0
        std::vector<hva::hvaBlob_t::Ptr> vecBlobInput =
            m_ctx.getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});
        
        if (vecBlobInput.empty()) 
            break;

        // input blob is not empty
        for (const auto& blob : vecBlobInput) {

            // read input buf from current blob
            hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(blob->get(0));
            HVA_ASSERT(ptrFrameBuf);

            HVA_DEBUG("Object select node %d on frameId %u and streamid %u with tag %d",  batchIdx, blob->frameId, blob->streamId, ptrFrameBuf->getTag());

            //
            // ptrFrameBuf->frameId： the relative frame number in one video.
            // blob->frameId： global frame number in one request, can contain multiple videos.
            //
            int video_frame_index = ptrFrameBuf->frameId;

            //
            // buffer tag from previous input field
            // 0: default value, 1: stands for the last frame of the video
            //
            unsigned tag = ptrFrameBuf->getTag();
            if ((video_frame_index + 1) % m_selectParams.frameInterval == 0 || tag == hvaBlobBufferTag::END_OF_REQUEST) {
                reset_selected();
                HVA_DEBUG("Object select node will start a new selection window on frameid %u and streamid %u", blob->frameId, blob->streamId);
            }

            // video_frame_index starts from 0
            switch (m_selectParams.strategy) {
                case ObjectSelectStrategy_t::ALL_IN_BEST_OUT:
                    if ((video_frame_index + 1) % m_selectParams.frameInterval == 0 || tag == hvaBlobBufferTag::END_OF_REQUEST) {
                        flag = true;
                        HVA_DEBUG("Object select node will select high quality objects on frameid %u and streamid %u", blob->frameId, blob->streamId);
                    }
                    break;
                case ObjectSelectStrategy_t::FIRST_IN_FIRST_OUT:
                    // do selection at each frame, until topK rois are collected within one selection window (i.e. m_selectParams.frameInterval)
                    flag = true;
                    HVA_DEBUG("Object select node will select high quality objects on frameid %u and streamid %u", blob->frameId, blob->streamId);
                    break;
                default:
                    HVA_ERROR("Unknown selection strategy received ObjectSelectStrategy_t::%d !", (int)m_selectParams.strategy);
            }

            // mark `depleting` status in hva pipeline
            m_ctx.getParentPtr()->holdDepleting();

            // collect all comming buffer and meta data during one selection interval
            collector->setResult(blob);

            /**
             * @brief object selection
             * flag == 1: start selection
             * 
             */
            if (flag) {

                try
                {
                    int collectedFrameCnt = collector->getFrameCnt();
                    int collectedROICnt = collector->getROICnt();

                    /// @brief none rois, no need to do selection, directly send out the last frame
                    if (collector->getROICnt() == 0) {
                        HVA_DEBUG("Object select node collected none rois within %u images on frameid %u and streamid %u", 
                                    collectedFrameCnt, blob->frameId, blob->streamId);
                        auto updatedBlobs = collector->getCollectedBlobs();
                        for (auto &curBlob : updatedBlobs) {
                            // send output to the subsequent nodes
                            HVA_DEBUG("Object select node sending blob with frameid %u and streamid %u", curBlob->frameId, curBlob->streamId);
                            m_ctx.sendOutput(curBlob, 0, std::chrono::milliseconds(0));
                            HVA_DEBUG("Object select node completed sent blob with frameid %u and streamid %u", curBlob->frameId, curBlob->streamId);
                        }
                        return;
                    }

                    // start processing, flush start time
                    auto procStart = std::chrono::steady_clock::now();
                    HVA_DEBUG("Object select node collected %d rois within %u images on frameid %u and streamid %u", 
                                collectedROICnt, collectedFrameCnt, blob->frameId, blob->streamId);
                    
                    unsigned curSelected = get_selected();
                    unsigned topK;
                    if (curSelected >= m_selectParams.topK) {
                        // 
                        // topK rois within this selection window is already achieved!
                        // 
                        topK = 0;
                        HVA_DEBUG("Object select node have selected enough rois: %d on frameid %u and streamid %u", 
                                  curSelected, blob->frameId, blob->streamId);
                    }
                    else {
                        // 
                        // Start selection and send out the blobs.
                        // 
                        topK = m_selectParams.topK - curSelected;
                        HVA_DEBUG("Object select node start to do quality selection on frameid %u and streamid %u...", blob->frameId, blob->streamId);
                    }

                    // 
                    // @brief runSelection means add ignore flag for each roi according to whether being selected or not
                    // if topK == 0, then it's used to initialize all ignore flag to false
                    // 
                    unsigned selecteCnt = collector->runSelection(topK, m_selectParams.trackletAware);
                    add_selected(selecteCnt);

                    auto updatedBlobs = collector->getCollectedBlobs();
                    for (auto &curBlob : updatedBlobs) {
                        // send output to the subsequent nodes
                        HVA_DEBUG("Object select node sending blob with frameid %u and streamid %u", curBlob->frameId, curBlob->streamId);
                        m_ctx.sendOutput(curBlob, 0, std::chrono::milliseconds(0));
                        HVA_DEBUG("Object select node completed sent blob with frameid %u and streamid %u", curBlob->frameId, curBlob->streamId);
                    }
                    HVA_DEBUG("Object select node complete quality selection on %u images, sended %u blobs to next node", collectedFrameCnt, updatedBlobs.size());
                    
                    // process done
                    auto procEnd = std::chrono::steady_clock::now();

                    // calculate node duration: selection
                    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(procEnd - procStart).count();
                    m_durationAve = (m_durationAve * (int)m_cntProcessEnd + duration) / ((int)m_cntProcessEnd + 1);
                    HVA_DEBUG("Object select node average duration is %ld ms, at processing cnt: %d", 
                                (int)m_durationAve, (int)m_cntProcessEnd);
                }
                catch(std::exception& e)
                {
                    std::cout << e.what() << std::endl;
                    HVA_DEBUG("Object select node exception error with frameid %u and streamid %u", blob->frameId, blob->streamId);

                    // catch error during inference, clear context
                    ptrFrameBuf->rois.clear();
                    HVA_DEBUG("Object select node sending blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
                    m_ctx.sendOutput(blob, 0, std::chrono::milliseconds(0));
                    HVA_DEBUG("Object select node completed sent blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
                    return;

                }
                catch(...)
                {
                    HVA_DEBUG("Object select node exception error with frameid %u and streamid %u", blob->frameId, blob->streamId);

                    // catch error during inference, clear context
                    ptrFrameBuf->rois.clear();
                    HVA_DEBUG("Object select node sending blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
                    m_ctx.sendOutput(blob, 0, std::chrono::milliseconds(0));
                    HVA_DEBUG("Object select node completed sent blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
                    return;
                }
            }
        }

    }   // keep reading blob data until frame_index meet the selection interval: `m_selectParams.frameInterval`
}

void ObjectSelectNodeWorker::Impl::init(){
    // todo
}

hva::hvaStatus_t ObjectSelectNodeWorker::Impl::rearm(){
    return hva::hvaSuccess;
}

hva::hvaStatus_t ObjectSelectNodeWorker::Impl::reset(){
    return hva::hvaSuccess;
}

ObjectSelectNodeWorker::ObjectSelectNodeWorker(hva::hvaNode_t *parentNode, const ObjectSelectParam_t& selectParams): 
        hva::hvaNodeWorker_t(parentNode), m_impl(new Impl(*this, selectParams)) {
    
}

ObjectSelectNodeWorker::~ObjectSelectNodeWorker(){

}

void ObjectSelectNodeWorker::process(std::size_t batchIdx){
    m_impl->process(batchIdx);
}

void ObjectSelectNodeWorker::init(){
    m_impl->init();
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(ObjectSelectNode, ObjectSelectNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}

}

}
