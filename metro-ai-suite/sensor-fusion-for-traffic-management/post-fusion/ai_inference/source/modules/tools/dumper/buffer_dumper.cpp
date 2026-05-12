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
    #include "modules/vaapi/utils.hpp"
#endif

#include "modules/tools/dumper/buffer_dumper.hpp"


namespace hce{

namespace ai{

namespace inference{

namespace tools{

bool dumpBufferImageByCVMat(const hva::hvaVideoFrameWithROIBuf_t::Ptr& buf, HceDatabaseMeta& meta, cv::Mat& outputMat) {
    if (!buf) {
        return false;
    }
    std::string dataStr;
    uint8_t* data_ptr;
    int width = buf->width;
    int height = buf->height;
    try {
        if (meta.bufType == HceDataMetaBufType::BUFTYPE_STRING) {
            dataStr = buf->get<std::string>();
            // check empty input
            if (dataStr.empty()) {
                return false;
            }
            data_ptr = (uint8_t*)dataStr.c_str();
        }
        else if (meta.bufType == HceDataMetaBufType::BUFTYPE_UINT8) {
            data_ptr = buf->get<uint8_t*>();
        }
#ifdef ENABLE_VAAPI
        else if (meta.bufType == HceDataMetaBufType::BUFTYPE_MFX_FRAME) {
            // HVA_ASSERT(meta.colorFormat == hce::ai::inference::ColorFormat::NV12);
            // TODO: support different mfxFrame type, mfxFrameSurface, VaapiImage...
            mfxFrameSurface1* surfPtr = buf->get<mfxFrameSurface1*>();
            WriteRawFrame_InternalMem(surfPtr, dataStr);
            data_ptr = (uint8_t*)dataStr.c_str();
            // width = surfPtr->Info.CropW;
            // height = surfPtr->Info.CropH;
        }
#endif
        else {
            HVA_ERROR("Unrecognized buffer type: %d", meta.bufType);
            return false;
        }
    } catch (const std::exception &e) {
        HVA_ERROR("Failed to get buffer data: %s\n",e.what());
        return false;
    }
    

    cv::Size cv_size(width, height);

    cv::Mat cv_mat;
    switch (meta.colorFormat) {
        case hce::ai::inference::ColorFormat::BGR:
            outputMat = cv::Mat(cv_size, CV_8UC3, data_ptr);
            break;
        case hce::ai::inference::ColorFormat::NV12:
            cv_size.height *= 1.5;
            cv_mat = cv::Mat(cv_size, CV_8UC1, data_ptr);
            cv::cvtColor(cv_mat, outputMat, cv::COLOR_YUV2BGR_NV12);
            break;
        case hce::ai::inference::ColorFormat::I420:
            cv_size.height *= 1.5;
            cv_mat = cv::Mat(cv_size, CV_8UC1, data_ptr);
            cv::cvtColor(cv_mat, outputMat, cv::COLOR_YUV2BGR_YV12);
            break;
        case hce::ai::inference::ColorFormat::BGRX:
            cv_mat = cv::Mat(cv_size, CV_8UC4, data_ptr);
            cv::cvtColor(cv_mat, outputMat, cv::COLOR_BGRA2BGR);
            break;
        default:
            HVA_ERROR("Unsupported format: %s", colorfmt_to_string(meta.colorFormat).c_str());
            return false;
    }

    return true;
}

} // namespace tools

} // namespace inference

} // namespace ai

} // namespace hce