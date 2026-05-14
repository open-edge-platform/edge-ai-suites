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

#ifndef __STORAGE_IMAGE_INPUT_NODE_H_
#define __STORAGE_IMAGE_INPUT_NODE_H_

#include <media_storage.h>
#include <s3_sdk.h>
#include <media_utility.h>
#include <opencv2/opencv.hpp>

#include "nodes/base/baseMediaInputNode.hpp"

namespace hce{

namespace ai{

namespace inference{

class StorageImageUploadNode : public hva::hvaNode_t{
public:
    
    StorageImageUploadNode(std::size_t totalThreadNum);

    virtual ~StorageImageUploadNode() override;

    /**
    * @brief Parse params, called by hva framework right after node instantiate.
    * @param config Configure string required by this node.
    */
    virtual hva::hvaStatus_t configureByString(const std::string& config) override;

    /**
    * @brief Constructs and returns a node worker instance: StorageImageUploadNodeWorker.
    * @param void
    */
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override;

private:
    hva::hvaConfigStringParser_t m_configParser;

    std::string m_mediaType;
    std::string m_dataSource;
    bool m_requireROI;
};

class StorageImageUploadNodeWorker : public hva::hvaNodeWorker_t{
public:
 StorageImageUploadNodeWorker(hva::hvaNode_t* parentNode,
                              const std::string& mediaType,
                              const std::string& dataSource,
                              bool requireROI);

 void init() override;

 /**
  * @brief Called by hva framework for each video frame, Run inference and pass
  * output to following node
  * @param batchIdx Internal parameter handled by hvaframework
  */
 void process(std::size_t batchIdx) override;

private:
    std::atomic<unsigned> m_ctr;

    float m_durationAve {0.0f};
    std::atomic<int32_t> m_cntProcessEnd{0};

    std::string m_mediaType;
    std::string m_dataSource;
    bool m_requireROI;

    std::string m_configmapFile;
    std::unique_ptr<hce::storage::Media_Storage> m_storageClient;
    boost::property_tree::ptree m_mediaAttribTree;

    /**
     * @brief generate media attrib
     * for example:
     * post_media_attributes = {"media_id": "0044","media_uri": 17301039306058ec87974571990a379e7696d0fb, 
     *                          "object_name": "media", "media_type_id": "01", "timestamp": "12345678"};      
    */
    bool generateMediaAttrib(const hva::hvaVideoFrameWithROIBuf_t::Ptr& ptrBuf, const std::string& URI,
                             const HceDatabaseMeta& originMeta, std::string& mediaAttrib, const std::string& originURI);

};

}

}

}
#endif /*__STORAGE_IMAGE_INPUT_NODE_H_*/
