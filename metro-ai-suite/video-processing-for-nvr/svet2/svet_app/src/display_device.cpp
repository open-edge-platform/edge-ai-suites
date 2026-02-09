/*

 * INTEL CONFIDENTIAL

 *

 * Copyright (C) 2023-2024 Intel Corporation

 *

 * This software and the related documents are Intel copyrighted materials, and your use of them is governed by the

 * express license under which they were provided to you ("License"). Unless the License provides otherwise, you may not

 * use, modify, copy, publish, distribute, disclose or transmit this software or the related documents without Intel's

 * prior written permission.

 *

 * This software and the related documents are provided as is, with no express or implied warranties, other than those

 * that are expressly stated in the License.

 */

#include <iostream>
#include <memory>
#include <string>
#include "display_device.h"
#include "spdlog/spdlog.h"
#include "svet_util.h"
#include "svet_cmd.h"

#ifdef VPPSDK_DISP
#include <vpp_display.h>
#endif

using namespace SVET_APP;
using std::cout;
using std::endl;
using std::string;
using spdlog::info;
using spdlog::debug;
using spdlog::error;
using spdlog::warn;
using std::shared_ptr;

int DisplayDevice::ShowDisplayDevices() {
    debug("SVET app: call VPP_DISPLAY_DEV_GetList");
#ifdef VPPSDK_DISP
    VPP_DISPLAY_Dev* pDevArray = nullptr;
    uint32_t deviceCount = 0;
    VPP_STATUS sts;
    sts = VPP_DISPLAY_DEV_GetList(&pDevArray, &deviceCount);
    if (sts == VPP_STATUS_SUCCESS && pDevArray && deviceCount > 0) {
        int devNum = deviceCount;
        cout<<"-------"<<devNum<<" displays conncted"<<"-------"<<endl;
        cout<<"display id"<<"\tdevice id"<<"\tMax resolution"<<"\tRefresh rate"<<"\tname\t"<<endl;

        for (int i = 0; i < devNum; i++ ) {
            cout<<i<<"\t\t"<<pDevArray[i].DevId<<"\t\t"<<pDevArray[i].pDevAttrs[0].HDisplay<<"X";
            cout<<pDevArray[i].pDevAttrs[0].VDisplay<<"\t"<<pDevArray[i].pDevAttrs[0].VRefresh;
            //cout<<"\t\t"<<pDevArray[i].pDevAttrs[0].Name<<endl;
            cout<<endl;
        }
        cout<<"Please use display id to specify which display you'd like to use"<<endl;
        VPP_DISPLAY_DEV_ReleaseList(pDevArray, deviceCount);
        return deviceCount;
    }
    else {
        error("VPPSDK: VPP_DISPLAY_DEV_GetList returns {} , device number:{}, device array:{}",
              (int)sts, deviceCount, (void *)pDevArray);
        VPP_DISPLAY_DEV_ReleaseList(pDevArray, deviceCount);
        return -1;
    }
#endif
    return 0;
}

int DisplayDevice::GetDisplayInfo(int id, DisplayAttr &info) {
    info.deviceId = -1;
    debug("SVET app: call VPP_DISPLAY_DEV_GetList");
#ifdef VPPSDK_DISP
    VPP_DISPLAY_Dev* pDevArray;
    uint32_t deviceCount;
    VPP_STATUS sts;
    sts = VPP_DISPLAY_DEV_GetList(&pDevArray, &deviceCount);
    if (sts == VPP_STATUS_SUCCESS && pDevArray && deviceCount > 0) {
        int devNum = deviceCount;
        debug("VPPSDK: VPP_DISPLAY_DEV_GetList returns {0} , device number:{1}, device array:{2}",
              int(sts), deviceCount, (void *)pDevArray);
        if (devNum <= id) {
            error("{0} : id({1}) isn't valid. It shall be {2} to {3}", __func__, id, 0, devNum - 1);
            return SVET_ERR_INVALID_ID;
        }
        info.deviceId = pDevArray[id].DevId;
        info.resolutionH= pDevArray[id].pDevAttrs[0].HDisplay;
        info.resolutionV = pDevArray[id].pDevAttrs[0].VDisplay;
        //info.name = string(pDevArray[id].pDevAttrs[0].Name);
        info.refreshR = pDevArray[id].pDevAttrs[0].VRefresh;
        VPP_DISPLAY_DEV_ReleaseList(pDevArray, deviceCount);
        return 0;
    }
    else {
        error("VPPSDK: VPP_DISPLAY_DEV_GetList returns {0} , device number:{1}, device array:{2}",
              int(sts), deviceCount, (void *)pDevArray);
        VPP_DISPLAY_DEV_ReleaseList(pDevArray, deviceCount);
        return -1;
    }
#else  //just for debug
    {
        info.deviceId = 123;
        info.resolutionV = 1080;
        info.resolutionH = 1920;
        info.name = std::string("Test");
        info.refreshR = 30;
    }
#endif
    return 0;
};

int DisplayDevice::Init(int id) {
    if (mState == NodeState::Initialized) {
        error("SVET app: display device with id({0}) has been initialized. Not need to re-initialize)", id);
        return -1;
    }
    if (GetDisplayInfo(id, mDispInfo) >= 0) {
        debug("SVET app: call VPP_DISPLAY_DEV_Create with device id {0}", mDispInfo.deviceId);
#ifdef VPPSDK_DISP
        VPP_STATUS sts = VPP_DISPLAY_DEV_Create(mDispInfo.deviceId);
        if (sts != VPP_STATUS_SUCCESS ) {
            error("SVET app: {0} : VPP_DISPLAY_DEV_Create return error {1}", __func__, int(sts));
            return SVET_ERR_VPPSDK_FAIL;
        }
#endif
        info("SVET app: DisplayDevice::init({0}) success", id);
        mId = id;
        mState = NodeState::Initialized;
        return 0;
    }
    return -1;
}

int DisplayDevice::Destroy() {

    if (mState == NodeState::Uninitialized)
        return 0;
    
    for (auto &it : mVideoLayers) {
        debug("SVET app: call VPP_DISPLAY_VIDEOLAYER_UnbindDev({}, {})", it.first, mDispInfo.deviceId);
        debug("SVET app: call VPP_DISPLAY_VIDEOLAYER_Destroy id({})", it.first);
#ifdef VPPSDK_DISP
        VPP_STATUS sts = VPP_DISPLAY_VIDEOLAYER_UnbindDev(it.first, mDispInfo.deviceId);
        if (sts != VPP_STATUS_SUCCESS) {
            warn("SVET app: {} VPP_DISPLAY_VIDEOLAYER_UnbindDev return error {}", __func__, sts);
        }
        sts = VPP_DISPLAY_VIDEOLAYER_Destroy(it.first);
        if (sts != VPP_STATUS_SUCCESS) {
            warn("SVET app: {} VPP_DISPLAY_VIDEOLAYER_Destroy {}", __func__, sts);
        }        
        it.second->state = VideoLayerState::Destroy;
#endif
    }
    debug(" SVET app: call VPP_DISPLAY_DEV_Destroy with device id {0}", mDispInfo.deviceId);
#ifdef VPPSDK_DISP
    VPP_STATUS sts = VPP_DISPLAY_DEV_Destroy(mDispInfo.deviceId);
    if (sts != VPP_STATUS_SUCCESS ) {
         error("SVET app: {0} : VPP_DISPLAY_DEV_Create return error {1}", __func__, int(sts));
    }
#endif
    mState = NodeState::Uninitialized;
    mId = -1;
    return 0;
}

int DisplayDevice::SetDisplayAttributes(int resW, int resH, int refreshR) {
    if (mState == NodeState::Uninitialized) {
        error("SVET app: {0} Display has been initialized!");
        return -1;
    }
    if (resW > mDispInfo.resolutionH || resH > mDispInfo.resolutionV || refreshR > mDispInfo.refreshR) {
        error("SVET app: The display resoluton {}X{} or refresh rate {} isn't supported."
              " Max supported resolution is {}X{}@{}", resW, resH, refreshR,
              mDispInfo.resolutionH, mDispInfo.resolutionV, mDispInfo.refreshR);
        return -1;
    }
    debug("SVET app: call VPP_DISPLAY_DEV_SetAttrs()");
#ifdef VPPSDK_DISP
    VPP_DISPLAY_Dev* pDevArray = nullptr;
    uint32_t deviceCount = 0;
    VPP_STATUS sts;

    int idx = -1;
    sts = VPP_DISPLAY_DEV_GetList(&pDevArray, &deviceCount);
    if (sts == VPP_STATUS_SUCCESS && pDevArray && deviceCount > 0) {
        int devNum = deviceCount;

        for (int i = 0; i < devNum; i++ ) {
            if (pDevArray[i].DevId == mDispInfo.deviceId) {
                idx = i;
                break;
            }
        }

        int modeIdx = -1;
        if (idx >= 0) {
            VPP_DISPLAY_Dev *displaAtt = pDevArray + idx;
            VPP_DISPLAY_DEV_Attrs* pDevAttrs = displaAtt->pDevAttrs;
            for (int i = 0; i < displaAtt->DevAttrsCount; i++) {
                if (pDevAttrs[i].HDisplay == resW && pDevAttrs[i].VDisplay == resH && pDevAttrs[i].VRefresh == refreshR)
                {
                    modeIdx = i;
                    info("SVET app: found display mode {}X{}@{} with index {}", resW, resH, refreshR, i);
                    break;
                }
            }
            if (modeIdx < 0) {
                spdlog::warn("SVET app: {0} display mode {0}X{1}@{2} not found. Will use {0}x{1}@{2]",
                             resW, resH, refreshR,
                             mDispInfo.resolutionH, mDispInfo.resolutionV, mDispInfo.refreshR);
                modeIdx = 0;
            }
            VPP_DISPLAY_DEV_Attrs attr = *(pDevAttrs + modeIdx);

            sts = VPP_DISPLAY_DEV_SetAttrs(mDispInfo.deviceId, (const VPP_DISPLAY_DEV_Attrs *)&attr);
            CHK_VPPSDK_RET(sts, "DisplayDevice::SetDisplayAttributes");

            VPP_DISPLAY_DEV_ReleaseList(pDevArray, deviceCount);
            pDevArray = nullptr;
        }
        if (pDevArray) {
            VPP_DISPLAY_DEV_ReleaseList(pDevArray, deviceCount);
            pDevArray = nullptr;
        }

        return 0;
    }
    else {
        error("VPPSDK: VPP_DISPLAY_DEV_GetList returns {0} , device number:{1}, device array:{2}",
              int(sts), deviceCount, (void *)pDevArray);
        VPP_DISPLAY_DEV_ReleaseList(pDevArray, deviceCount);
        pDevArray = nullptr;
        return -1;
    }
#endif

    return 0;
}

int DisplayDevice::CreateVideoLayer(VideoLayerInfo &attr, int id) {
    debug("SVET app: call VPP_DISPLAY_VIDEOLAYER_Create with id({0})", id);
    debug("SVET app: call VPP_DISPLAY_VIDEOLAYER_BindDev with deviceid({0})", mDispInfo.deviceId);
    debug("SVET app: call VPP_DISPLAY_VIDEOLAYER_SetAttrs with {0}x{1}@{2}, fps:{}, with pixel format {3:x}, pb size {4}",
          attr.rect.w, attr.rect.h, attr.refreshRate, attr.fps, attr.pixelFormat, attr.bufferSize);
#ifdef VPPSDK_DISP

    VPP_STATUS sts = VPP_DISPLAY_VIDEOLAYER_Create(id);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_VIDEOLAYER_Create");

    VPP_DISPLAY_PIXEL_FORMAT pixelFormat;

    VideoFrameType format = static_cast<VideoFrameType>(attr.pixelFormat);

    switch (format) {
        case VideoFrameType::FOURCC_NV12:
            pixelFormat = PIXEL_FORMAT_NV12;
            break;
        case VideoFrameType::FOURCC_RGB4:
            pixelFormat = PIXEL_FORMAT_RGB_8888;
            break;
        default:
            error("SVET app: {0} not support pixel format {1:x}", __func__, attr.pixelFormat);
            VPP_DISPLAY_VIDEOLAYER_Destroy(id);
            return SVET_ERR_PIXELFORMMAT_UNSUPPORT;
            break;
    }
    
    uint16_t x = attr.rect.x;
    uint16_t y = attr.rect.y;
    uint16_t w = attr.rect.w;
    uint16_t h = attr.rect.h;
    VPP_Size vppSize = {w, h};

    VPP_DISPLAY_VIDEOLAYER_Attrs vlAttr = { {x, y, w, h },
                                          vppSize,                                          
                                          //pixelFormat,
                                          static_cast<int32_t>(attr.fps) };

    sts = VPP_DISPLAY_VIDEOLAYER_SetAttrs(id, (const VPP_DISPLAY_VIDEOLAYER_Attrs*) &vlAttr);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_VIDEOLAYER_SetAttrs");

    if (attr.tilenum > 0) {
        sts = VPP_DISPLAY_VIDEOLAYER_SetNumOfTiles(id, attr.tilenum);
        CHK_VPPSDK_RET(sts, "VPP_DISPLAY_VIDEOLAYER_SetNumOfTiles");
    }

    sts = VPP_DISPLAY_VIDEOLAYER_BindDev(id, mDispInfo.deviceId);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_VIDEOLAYER_BindDev");
#endif


    shared_ptr<VideoLayerInfo> ptr = std::make_shared<VideoLayerInfo>(attr);
    mVideoLayers[id] = ptr;
    return 0;
}

DisplayDevice::~DisplayDevice() {
    try {
        if (mState > NodeState::Uninitialized) {
            if (mState == NodeState::Play) {
                Stop();
            }
            Destroy();
        }
    } catch (...) {
        std::cerr<<"SVET app: "<<__func__<<" unknown exception"<<std::endl;
    }
}

int DisplayDevice::StartDisp() {
    if (mState != NodeState::Play) {
        debug("SVET app: call VPP_DISPLAY_DEV_Start device id({})", mDispInfo.deviceId);
#ifdef VPPSDK_DISP
        VPP_STATUS sts = VPP_DISPLAY_DEV_Start(mDispInfo.deviceId);
        CHK_VPPSDK_RET(sts, "VPP_DISPLAY_DEV_Start");
        mState = NodeState::Play;
#endif
    }
    return 0;
}

int DisplayDevice::Start() {

    for (auto &it : mVideoLayers) {
        if (it.second->state != VideoLayerState::Play) {
            debug("SVET app: call VPP_DISPLAY_VIDEOLAYER_Start id({})", it.first);
#ifdef VPPSDK_DISP
            VPP_STATUS sts = VPP_DISPLAY_VIDEOLAYER_Start(it.first);
            CHK_VPPSDK_RET(sts, "VPP_DISPLAY_VIDEOLAYER_Start");
            it.second->state = VideoLayerState::Play;
#endif
        }
    }
    if (mState != NodeState::Play) {
        debug("SVET app: call VPP_DISPLAY_DEV_Start device id({})", mDispInfo.deviceId);
#ifdef VPPSDK_DISP
        VPP_STATUS sts = VPP_DISPLAY_DEV_Start(mDispInfo.deviceId);
        CHK_VPPSDK_RET(sts, "VPP_DISPLAY_DEV_Start");
        mState = NodeState::Play;
#endif
    }
    return 0;
}

int DisplayDevice::Stop() {
    for (auto &it : mVideoLayers) {
        debug("SVET app: call VPP_DISPLAY_VIDEOLAYER_Stop id({})", (int)it.first);
#ifdef VPPSDK_DISP
        VPP_STATUS sts = VPP_DISPLAY_VIDEOLAYER_Stop(it.first);
        CHK_VPPSDK_RET(sts, "VPP_DISPLAY_VIDEOLAYER_Stop");
            it.second->state = VideoLayerState::Stop;
#endif
    }
    debug("SVET app: call VPP_DISPLAY_DEV_Stop device id({})", mDispInfo.deviceId);
#ifdef VPPSDK_DISP
    VPP_STATUS sts = VPP_DISPLAY_DEV_Stop(mDispInfo.deviceId);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_DEV_Stop");
    mState = NodeState::Stop;
#endif
    return 0;
}

int DisplayDevice::Stop(int videoLayer) {
    auto res = mVideoLayers.find(videoLayer);
    if ( res != mVideoLayers.end())
    {
        debug("SVET app: call VPP_DISPLAY_VIDEOLAYER_Stop id({})", videoLayer);
#ifdef VPPSDK_DISP
        VPP_STATUS sts = VPP_DISPLAY_VIDEOLAYER_Stop(videoLayer);
        CHK_VPPSDK_RET(sts, "VPP_DISPLAY_VIDEOLAYER_Stop");
            res->second->state = VideoLayerState::Stop;
#endif

    }
    return 0;
}

int DisplayDevice::Start(int videoLayer) {
    auto res = mVideoLayers.find(videoLayer);
    if ( res != mVideoLayers.end())
    {
        debug("SVET app: call VPP_DISPLAY_VIDEOLAYER_Start id({})", videoLayer);
#ifdef VPPSDK_DISP
        VPP_STATUS sts = VPP_DISPLAY_VIDEOLAYER_Start(videoLayer);
        CHK_VPPSDK_RET(sts, "VPP_DISPLAY_VIDEOLAYER_Start");
            res->second->state = VideoLayerState::Play;
#endif

    }
    return 0;
}

