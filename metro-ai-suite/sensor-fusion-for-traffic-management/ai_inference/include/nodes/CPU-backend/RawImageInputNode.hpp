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

#ifndef __RAW_IMAGE_INPUT_NODE_H_
#define __RAW_IMAGE_INPUT_NODE_H_

#include "nodes/base/baseMediaInputNode.hpp"

namespace hce{

namespace ai{

namespace inference{

class RawImageInputNode : public baseMediaInputNode{
public:
    
    RawImageInputNode(std::size_t totalThreadNum);

    virtual ~RawImageInputNode() {};

    /**
     * @brief Constructs and returns a node worker instance: RawImageInputNodeWorker.
     * @param void
     */
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override;

private:
    hva::hvaConfigStringParser_t m_configParser;
};

class RawImageInputNodeWorker : public baseMediaInputNodeWorker{
public:

    RawImageInputNodeWorker(hva::hvaNode_t* parentNode);

    void init() override;

    virtual const std::string nodeClassName() const override{ return "RawImageInputNode";};

private:

    /**
     * @brief to process media content from blob
     * @param buf buffer from blob, should be raw image string
     * @param content acquired media content
     * @param meta HceDatabaseMeta, can be updated
     * @param roi roi region, default be [0, 0, 0, 0]
     */
    virtual readMediaStatus_t processMediaContent(const std::string& buf, std::string& content,
                                    HceDatabaseMeta& meta, TimeStamp_t& timeMeta, hva::hvaROI_t& roi, unsigned order = 0);
};

}

}

}
#endif /*__RAW_IMAGE_INPUT_NODE_H_*/
