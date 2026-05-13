/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2022 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef __BASE_MEDIA_INPUT_NODE_H_
#define __BASE_MEDIA_INPUT_NODE_H_

#include <iostream>
#include <memory>
#include <mutex>
#include <condition_variable>
#include <string>
#include <vector>
#include <time.h>
#include <sys/timeb.h>

#include <inc/api/hvaPipeline.hpp>
#include <inc/util/hvaConfigStringParser.hpp>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>

#include <boost/property_tree/json_parser.hpp>

#include "nodes/databaseMeta.hpp"

namespace hce{

namespace ai{

namespace inference{

enum readMediaStatus_t{
    Success = 0,
    Finish,
    Failure
};

// Base class for input node
class baseMediaInputNode : public hva::hvaNode_t{
public:
    
    baseMediaInputNode(std::size_t totalThreadNum);

    virtual ~baseMediaInputNode() override;

    virtual hva::hvaStatus_t rearm() override;

    virtual hva::hvaStatus_t reset() override;
};

// Base class for input node workers
// All derived classes share with process() in this base class
// processMediaContent should be implemented in derived classes.
class baseMediaInputNodeWorker : public hva::hvaNodeWorker_t{
public:
    using BatchedMedias = std::vector<std::string>;

    baseMediaInputNodeWorker(hva::hvaNode_t* parentNode);

    void init() override;

    /**
     * @brief Frame index increased for every coming frame, will be called at the process()
     * @param void
     */
    unsigned fetch_increment();

    /**
     * @brief Called by hva framework for each video frame, Run inference and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx) override;

    hva::hvaStatus_t rearm() override;
    hva::hvaStatus_t reset() override;

    virtual const std::string nodeClassName() const = 0;

    /**
     * @brief generate media_uri with respect to `media_type` and `data_source`
     * @param mediaType video or image
     * @param dataSource vehicle
     * @param URI generated uri, schema: Hash(media_type,4) + Hash(data_source,4) + content(32)
     */
    bool generateMediaURI(const std::string& mediaType,
                            const std::string& datasource,
                            const std::string& content, std::string& URI);
    
    /**
     * Timestamp is the unix timestamp in ms
     */
    uint64_t generateCurTimeStamp();

protected:
    /**
     * @brief Send empty buf to next node
     * @param blob input blob data with empty buf
     * @param isEnd flag for coming request
     * @param meta databaseMeta
     */
    void sendEmptyBuf(hva::hvaBlob_t::Ptr blob, bool isEnd, const HceDatabaseMeta& meta = HceDatabaseMeta());

private:
    /**
     * @brief to process media content from blob, should be implemented by specific derived class.
     * @param buf buffer from blob
     * @param content acquired media content
     * @param meta HceDatabaseMeta, can be updated
     * @param roi roi region, default be [0, 0, 0, 0]
     */
    virtual readMediaStatus_t processMediaContent(const std::string& buf,
                                     std::string& content,
                                     HceDatabaseMeta& meta,
                                     TimeStamp_t& timeMeta,
                                     hva::hvaROI_t& roi, unsigned order = 0) = 0;

    std::atomic<unsigned> m_ctr;
    int m_workStreamId;
};

}

}

}
#endif /*__BASE_MEDIA_INPUT_NODE_H_*/
