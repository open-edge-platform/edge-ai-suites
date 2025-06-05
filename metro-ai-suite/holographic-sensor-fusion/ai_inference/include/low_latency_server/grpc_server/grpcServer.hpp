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

#ifndef HCE_AI_INF_GPRC_SERVER_HPP
#define HCE_AI_INF_GPRC_SERVER_HPP

#include "nodes/base/baseResponseNode.hpp"


namespace hce{

namespace ai{

namespace inference{

class HCE_AI_DECLSPEC GrpcServer final{
private:
    class _CommHandle;

public:
    using Handle = std::shared_ptr<_CommHandle>;

    struct CommConfig{
        std::string serverAddr;
        unsigned threadPoolSize = 1;
    };

    ~GrpcServer();

    GrpcServer(const GrpcServer&) = delete;

    GrpcServer(GrpcServer&&) = delete;

    GrpcServer& operator=(const GrpcServer&) = delete;

    GrpcServer& operator=(GrpcServer&&) = delete;

    static GrpcServer& getInstance();

    hceAiStatus_t init(const CommConfig& config);

    hceAiStatus_t start();

    hceAiStatus_t reply(Handle handle, const baseResponseNode::Response& reply);

    hceAiStatus_t replyFinish(Handle handle);

    void stop();

private:
    GrpcServer();

    class Impl;
    std::unique_ptr<Impl> m_impl;

};

}

}

}

#endif //#ifndef HCE_AI_INF_GPRC_SERVER_HPP
