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

#ifndef HCE_AI_INF_COMMON_HPP
#define HCE_AI_INF_COMMON_HPP

#include <string>
#include <memory>
#include <stdexcept>
#include <iostream>
#include <regex>

#if defined(__linux__)
#define HCE_AI_DECLSPEC 
#elif defined(WIN32)
#define HCE_AI_DECLSPEC __declspec(dllexport) 
#endif

#define _HCE_AI_PP_CONCAT(A, B) A##B
#define HCE_AI_PP_CONCAT(A, B) _HCE_AI_PP_CONCAT(A, B)

#define HCE_AI_ASSERT(cond) do{if(!(cond)){::hce::ai::inference::hceAiAssertFail(#cond, __LINE__, __FILE__, \
    __func__);}} while(false);

namespace hce{

namespace ai{

namespace inference{

enum HCE_AI_DECLSPEC hceAiStatus_t{
    hceAiWarningUnspecified = INT16_MIN,
    hceAiHttpServerStopByExternal,
    hceAiHttpServerStopByIdle,

    hceAiSuccess = 0,
    hceAiFailure,
    hceAiFailureUnspecified,
    hceAiBadArgument,
    hceAiSocketListenFailure,
    hceAiInvalidCall,
    hceAiServiceNotReady
};

// TODO  duplicated with image_info.h: ImageFormat
// considering transfer ColorFormat to ImageFormat
/**
 * @enum ColorFormat
 *
 * Represents Color formats.
 *     I420:
 *          For one I420 pixel: YYYYYYYY UU VV
 *          For n-pixel I420 frame: Y×8×n U×2×n V×2×n
 *     NV12:
 *          For one NV12 pixel: YYYYYYYY UVUV
 *          For n-pixel NV12 frame: Y×8×n (UV)×2×n
 *     It can be helpful to think of NV12 as I420 with the U and V planes interleaved.
 */
enum HCE_AI_DECLSPEC ColorFormat { BGR, NV12, BGRX, GRAY, I420 };     // 

/**
 * @enum TrackingStatus
 *
 */
enum HCE_AI_DECLSPEC TrackingStatus {
    NONE = 0,                       /**< The object is undefined. */
    NEW = 1,                        /**< The object is newly added. */
    TRACKED = 2,                    /**< The object is being tracked. */
    LOST = 3,                       /**< The object gets lost now. The object can be tracked again automatically(long term tracking) or by
                                        specifying detected object manually(short term and zero term tracking). */
    DEAD = -1                       /**< The object is dead. */
};

/**
 * @enum Buffer Tag for hva::hvaBlob_t::Ptr
*/
enum HCE_AI_DECLSPEC hvaBlobBufferTag {
    NORMAL = 0,                         /**< normal buffer in hvaBlob. default*/
    END_OF_REQUEST = 1                  /**< end of the request in current pipeline, 
                                             for output node, it's time to send finish flag to client*/  
};

HCE_AI_DECLSPEC void hceAiAssertFail(const char* cond, int line, const char* file, const char* func);

HCE_AI_DECLSPEC std::string colorfmt_to_string(ColorFormat code);

HCE_AI_DECLSPEC std::string buffertag_to_string(unsigned code);

HCE_AI_DECLSPEC std::string buffertag_to_string(hvaBlobBufferTag code);

}

#define HCE_AI_CHECK_RETURN_IF_FAIL(cond, ret) do{if(!(cond)){ std::cerr << #cond << " failed!" << std::endl; return ret;}} while(false);


}

}

#endif //#ifndef HCE_AI_INF_COMMON_HPP
