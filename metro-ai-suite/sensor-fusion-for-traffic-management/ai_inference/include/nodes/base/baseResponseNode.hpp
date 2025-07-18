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

#ifndef HCE_AI_BASE_RESPONSE_NODE_HPP
#define HCE_AI_BASE_RESPONSE_NODE_HPP

#include <inc/api/hvaPipeline.hpp>

#include "common/common.hpp"

namespace hce{

namespace ai{

namespace inference{

class HCE_AI_DECLSPEC baseResponseNode : public hva::hvaNode_t{
public:
    struct ResponseData{
        std::string stringData;
        size_t length;
        std::string binaryData;
    };

    struct Response{
        int status;
        std::unordered_map<std::string, ResponseData> responses;
        std::string message; 
    };

    class HCE_AI_DECLSPEC EmitListener{
    public:
        EmitListener();

        virtual ~EmitListener();

        virtual void onEmit(Response res, const baseResponseNode* node, void* data) = 0;

        virtual void onFinish(const baseResponseNode* node, void* data) = 0;
    };

    baseResponseNode(std::size_t inPortNum, std::size_t outPortNum, std::size_t totalThreadNum);

    virtual ~baseResponseNode();

    virtual hva::hvaStatus_t prepare();

    void registerEmitListener(std::shared_ptr<EmitListener> listner);

    void clearAllEmitListener();

    virtual bool emitOutput(Response res, const baseResponseNode* node, void* data);

    virtual bool emitFinish(const baseResponseNode* node, void* data);

    /**
    * @brief return the human-readable name of this node class
    * 
    * @param void
    * @return node class name
    */
    virtual const std::string nodeClassName() const = 0;

    /**
     * @brief maintain finish-flag counter
     * 
    */
    void addEmitFinishFlag();

    /**
     * @brief check whether to trigger emitFinish()
     * 
    */
    bool isEmitFinish();

private: 
    class Impl;
    std::unique_ptr<Impl> m_impl;
};


class HCE_AI_DECLSPEC baseResponseNodeWorker : public hva::hvaNodeWorker_t{

public:
    baseResponseNodeWorker(hva::hvaNode_t* parentNode);

    /**
     * @brief validate input
     * @param blob current input
     * @return output node workers should be stream-aware.
     * 
    */
    bool validateStreamInput(const hva::hvaBlob_t::Ptr& blob);

protected:
    std::string m_nodeName;

private:
    int m_workStreamId;

};

}

}

}

#endif //#ifndef HCE_AI_BASE_RESPONSE_NODE_HPP
