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

#include <common/common.hpp>

namespace hce{

namespace ai{

namespace inference{

void hceAiAssertFail(const char* cond, int line, const char* file, const char* func){
    fprintf(stderr,
            "%s:%d: Assertion \"%s\" in function \"%s\" failed\n",
            file, line, cond, func);
    fflush(stderr);
    abort();
}


std::string colorfmt_to_string(ColorFormat code) {
    switch(code)
    {
        case ColorFormat::BGR:
            return "BGR";
        case ColorFormat::BGRX:
            return "BGRX";
        case ColorFormat::GRAY:
            return "GRAY";
        case ColorFormat::I420:
            return "I420";
        case ColorFormat::NV12:
            return "NV12";
        default:
            break;
    }

    std::string ret("<unknown ");
    ret += std::to_string(code) + ">";
    return ret;
}

std::string buffertag_to_string(unsigned code) {
    return buffertag_to_string((hvaBlobBufferTag)code);
}

std::string buffertag_to_string(hvaBlobBufferTag code) {
    switch(code)
    {
        case hvaBlobBufferTag::NORMAL:
            return "NORMAL";
        case hvaBlobBufferTag::END_OF_REQUEST:
            return "END_OF_REQUEST";
        default:
            break;
    }

    std::string ret("<unknown ");
    ret += std::to_string(code) + ">";
    return ret;
}

}

}

}