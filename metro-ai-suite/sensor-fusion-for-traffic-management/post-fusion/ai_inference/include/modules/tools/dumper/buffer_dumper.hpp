/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2024 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#pragma once

#ifdef ENABLE_VAAPI
    #include <va/va.h>
    #include <va/va_backend.h>
#endif

#include <opencv2/opencv.hpp>
#include <opencv2/imgproc.hpp>

#include "nodes/databaseMeta.hpp"
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>


namespace hce{

namespace ai{

namespace inference{

namespace tools{

bool dumpBufferImageByCVMat(const hva::hvaVideoFrameWithROIBuf_t::Ptr& buf, HceDatabaseMeta& meta, cv::Mat& outputMat);


} // namespace tools

} // namespace inference

} // namespace ai

} // namespace hce