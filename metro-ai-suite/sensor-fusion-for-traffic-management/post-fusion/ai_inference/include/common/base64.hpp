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

#ifndef HCE_AI_INF_BASE64_HPP
#define HCE_AI_INF_BASE64_HPP
#include <boost/algorithm/string.hpp>
#include <boost/archive/iterators/binary_from_base64.hpp>
#include <boost/archive/iterators/base64_from_binary.hpp>
#include <boost/archive/iterators/transform_width.hpp>
#include <common/common.hpp>
#include <boost/beast/core/detail/base64.hpp>

namespace hce{

namespace ai{

namespace inference{

std::string base64DecodeStrToStr(const std::string &val);

std::string base64EncodeStrToStr(const std::string &val);

size_t base64EncodeBufferToString(std::string& dst, void const* src, size_t len);

size_t base64DecodeStringToBuffer(std::string& src, void* dst);

}

}

}
#endif