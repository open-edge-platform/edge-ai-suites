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

#include "common/base64.hpp"
#include "common/common.hpp"

namespace hce{

namespace ai{

namespace inference{

std::string base64DecodeStrToStr(const std::string &val)
{
    using namespace boost::archive::iterators;
    using It = transform_width<binary_from_base64<std::string::const_iterator>, 8, 6>;
    return boost::algorithm::trim_right_copy_if(std::string(It(std::begin(val)), It(std::end(val))), [](char c) {
        return c == '\0';
    });
}

std::string base64EncodeStrToStr(const std::string &val)
{
    using namespace boost::archive::iterators;
    using It = base64_from_binary<transform_width<std::string::const_iterator, 6, 8>>;
    auto tmp = std::string(It(std::begin(val)), It(std::end(val)));
    return tmp.append((3 - val.size() % 3) % 3, '=');
}

size_t base64EncodeBufferToString(std::string& dst, void const* src, size_t len)
{
  using namespace boost::beast::detail::base64;
  void * destEncodeBuffer = malloc(encoded_size(len));
  HCE_AI_ASSERT(destEncodeBuffer);
  encode(destEncodeBuffer, src, len);
  dst.assign((char*)destEncodeBuffer, (char*)destEncodeBuffer + encoded_size(len));
  free(destEncodeBuffer);
  return hceAiSuccess;
}

size_t base64DecodeStringToBuffer(std::string& src, void* dst)
{
  using namespace boost::beast::detail::base64;
  decode(dst, src.data(), src.length());
  return hceAiSuccess;
}

}

}

}