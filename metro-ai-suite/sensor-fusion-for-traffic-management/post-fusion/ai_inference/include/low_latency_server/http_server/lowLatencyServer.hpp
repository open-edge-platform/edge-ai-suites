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

#ifndef HCE_AI_INF_LL_LOW_LATENCY_SERVER_HPP
#define HCE_AI_INF_LL_LOW_LATENCY_SERVER_HPP

#include "common/common.hpp"

namespace hce{

namespace ai{

namespace inference{

class HCE_AI_DECLSPEC HttpServerLowLatency final{
private:
    struct _ClientDes;
    
public:
    using ClientDes = std::shared_ptr<_ClientDes>;

    ~HttpServerLowLatency();

    HttpServerLowLatency(const HttpServerLowLatency&) = delete;

    HttpServerLowLatency(HttpServerLowLatency&&) = delete;

    HttpServerLowLatency& operator=(const HttpServerLowLatency&) = delete;

    HttpServerLowLatency& operator=(HttpServerLowLatency&&) = delete;

    static HttpServerLowLatency& getInstance();

    hceAiStatus_t init(const std::string& address, unsigned port);

    hceAiStatus_t run();

    hceAiStatus_t reply(ClientDes client, unsigned code, const std::string& reply);

    void stop();

private:
    HttpServerLowLatency();

    class Impl;
    std::unique_ptr<Impl> m_impl;

};

}

}

}

#endif //#ifndef HCE_AI_INF_LL_LOW_LATENCY_SERVER_HPP
