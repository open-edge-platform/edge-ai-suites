/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2022 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef HCE_AI_INF_RESTFUL_MESSAGE_HPP
#define HCE_AI_INF_RESTFUL_MESSAGE_HPP

#include <common/common.hpp>

#include <vector>

namespace hce{

namespace ai{

namespace inference{

struct HCE_AI_DECLSPEC RESTfulBinary{
    char* data;
    std::size_t length;
};

struct HCE_AI_DECLSPEC RESTfulMessage{
    std::string json;
    std::vector<RESTfulBinary> binary; // may be empty
};

}

}

}

#endif //#ifndef HCE_AI_INF_RESTFUL_MESSAGE_HPP
