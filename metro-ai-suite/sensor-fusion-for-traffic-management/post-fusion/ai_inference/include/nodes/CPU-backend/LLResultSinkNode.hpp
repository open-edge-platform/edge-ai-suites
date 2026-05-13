/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2023 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef HCE_AI_INF_LL_RESULT_SINK_NODE_HPP
#define HCE_AI_INF_LL_RESULT_SINK_NODE_HPP

#include <mutex>

#include <boost/property_tree/json_parser.hpp>

#include <inc/util/hvaConfigStringParser.hpp>

#include "nodes/databaseMeta.hpp"
#include "nodes/base/baseResponseNode.hpp"
#include "storage_sdk/hbase_c++_client/feature_storage.h"

namespace hce{

namespace ai{

namespace inference{

class HCE_AI_DECLSPEC LLResultSinkNodeWorker : public baseResponseNodeWorker{
public:
    LLResultSinkNodeWorker(hva::hvaNode_t* parentNode);

    /**
     * @brief Called by hva framework for each video frame, Run inference and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    virtual void process(std::size_t batchIdx) override;

    /**
    * @brief Called by hva framework for each video frame, will be called only once before the usual process() being called
    * @param batchIdx Internal parameter handled by hvaframework
    */
    virtual void processByFirstRun(std::size_t batchIdx) override;

private:
    /**
     * @brief construct feature set, to put hvaROI_t to featureSet the format defined by storage API
    */
    static void constructFeatureSet(const std::vector<hva::hvaROI_t>& rois, HceDatabaseMeta& meta,
                                    hce::storage::FeatureSet& featureSet);
    
    /**
     * @brief serialize vector data to string: "{xx, yy, ...}"
     * @param content vector content
     * @return std::string
    */
    template <typename T>
    std::string vectorToString(std::vector<T> content)
    {
        std::string vector_str;
        for (const T val : content) {
            vector_str = vector_str + std::to_string(val) + ",";
        }
        vector_str = "{" + vector_str.substr(0, vector_str.size() - 1) + "}";
        return vector_str;
    };

    boost::property_tree::ptree m_jsonTree;

};

class HCE_AI_DECLSPEC LLResultSinkNode : public baseResponseNode{
public:

    LLResultSinkNode(std::size_t totalThreadNum);

    ~LLResultSinkNode() = default;

    /**
    * @brief Parse params, called by hva framework right after node instantiate.
    * @param config Configure string required by this node.
    */
    virtual hva::hvaStatus_t configureByString(const std::string& config) override;
    
    /**
    * @brief prepare and intialize this hvaNode_t instance
    * 
    * @param void
    * @return hvaSuccess if success
    */
    virtual hva::hvaStatus_t prepare();
    
    /**
    * @brief Constructs and returns a node worker instance: LLResultSinkNodeWorker.
    * @param void
    */
    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override; 

    virtual const std::string nodeClassName() const override{ return "LLResultSinkNode";};

private: 
    hva::hvaConfigStringParser_t m_configParser;
    
};

}

}

}

#endif //#ifndef HCE_AI_INF_LL_RESULT_SINK_NODE_HPP