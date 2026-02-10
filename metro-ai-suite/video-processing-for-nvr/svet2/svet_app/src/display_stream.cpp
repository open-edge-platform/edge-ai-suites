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

#ifdef VPPSDK_DISP
#include <vpp_display.h>
#include <vpp_common.h>
#endif
#include "spdlog/spdlog.h"
#include "display_stream.h"
#include "svet_util.h"

using std::cout;
using std::endl;
using namespace SVET_APP;
using spdlog::debug;
using spdlog::error;

DisplayStream::DisplayStream()  {

}

int DisplayStream::create(DispStreamPara *para, int fps) {
    debug("SVET app: call VPP_DISPLAY_STREAM_Create({}, {})", para->videoLayer, para->id);
    debug("SVET app: call VPP_DISPLAY_STREAM_SetAttr {},{} {}.{}, fps:{}", para->x, para->y, para->w, para->h, fps);
#ifdef VPPSDK_DISP
    VPP_STATUS sts = VPP_DISPLAY_STREAM_Create(para->videoLayer, para->id);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_STREAM_Create");
    VPP_DISPLAY_STREAM_Attrs attrs = {{para->x, para->y, para->w, para->h}};
    sts = VPP_DISPLAY_STREAM_SetAttrs(para->videoLayer, para->id, &attrs);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_STREAM_SetAttrs");
    sts = VPP_DISPLAY_STREAM_SetFrameRate(para->videoLayer, para->id, fps);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_STREAM_SetFrameRate");
    if (para->tileid > -1) {
        sts = VPP_DISPLAY_STREAM_SetTileId(para->videoLayer, para->id, para->tileid);
        CHK_VPPSDK_RET(sts, "VPP_DISPLAY_STREAM_SetTileId");
        sts = VPP_DISPLAY_VIDEOLAYER_EnableTileComposition(para->videoLayer);
        CHK_VPPSDK_RET(sts, "VPP_DISPLAY_VIDEOLAYER_EnableTileComposition");
    }
#endif
    return 0;
}

int DisplayStream::destroy(int streamId, int videoLayerId) {
    debug("SVET app: call VPP_DISPLAY_STREAM_Destroy({}, {})",  videoLayerId, streamId);
#ifdef VPPSDK_DISP
    VPP_STATUS sts = VPP_DISPLAY_STREAM_Destroy(videoLayerId, streamId);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_STREAM_Destroy");
#endif
    return 0;
}
int DisplayStream::pause(DispChCtrlPara *para) {
    debug("SVET app: call VPP_DISPLAY_STREAM_Pause({}, {})", para->videoLayer , para->id);
#ifdef VPPSDK_DISP
    VPP_STATUS sts = VPP_DISPLAY_STREAM_Pause(para->videoLayer , para->id);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_STREAM_Pause");
#endif
    return 0;
}

int DisplayStream::resume(DispChCtrlPara *para) {
    debug("SVET app: call VPP_DISPLAY_STREAM_Resume({}, {})", para->videoLayer , para->id);
#ifdef VPPSDK_DISP
    VPP_STATUS sts = VPP_DISPLAY_STREAM_Resume(para->videoLayer , para->id);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_STREAM_Resume");
#endif
    return 0;
}

int DisplayStream::hide(DispChCtrlPara *para) {
    debug("SVET app: call VPP_DISPLAY_STREAM_Hide({}, {})", para->videoLayer , para->id);
#ifdef VPPSDK_DISP
    VPP_STATUS sts = VPP_DISPLAY_STREAM_Hide(para->videoLayer , para->id);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_STREAM_Hide");
#endif

    return 0;
}

int DisplayStream::show(DispChCtrlPara *para) {
    debug("SVET app: call VPP_DISPLAY_STREAM_Show({}, {})", para->videoLayer , para->id);
#ifdef VPPSDK_DISP
    VPP_STATUS sts = VPP_DISPLAY_STREAM_Show(para->videoLayer , para->id);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_STREAM_Show");
#endif
    return 0;
}

int DisplayStream::zoomOut(DispChCtrlPara *para) {
    debug("SVET app: call VPP_DISPLAY_STREAM_SetZoomInAttr({}, {})",
          para->videoLayer , para->id);
#ifdef VPPSDK_DISP
    VPP_DISPLAY_STREAM_ZoomInAttrs attr;
    attr.Type = VPP_DISPLAY_ZOOM_IN_RECT;
    attr.Rect = {0, 0, 0, 0};

    VPP_STATUS sts = VPP_DISPLAY_STREAM_SetZoomInAttr(para->videoLayer , para->id, &attr);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_STREAM_SetZoomInAttr");
#endif
    return 0;
}

int DisplayStream::zoomIn(DispChCtrlPara *para) {
    debug("SVET app: call VPP_DISPLAY_STREAM_SetZoomInAttr({}, {}, ({}, {}, {}, {})",
          para->videoLayer , para->id, para->x, para->y, para->w, para->h);
#ifdef VPPSDK_DISP
    VPP_DISPLAY_STREAM_ZoomInAttrs attr;
    attr.Type = VPP_DISPLAY_ZOOM_IN_RECT;
    attr.Rect = {para->x, para->y, para->w, para->h};

    VPP_STATUS sts = VPP_DISPLAY_STREAM_SetZoomInAttr(para->videoLayer , para->id, &attr);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_STREAM_SetZoomInAttr");
#endif
    return 0;
}

int DisplayStream::addOsd(DispChCtrlPara *para) {
    debug("SVET app: call VPP_DISPLAY_STREAM_Pause({}, {})", para->videoLayer , para->id);
#ifdef VPPSDK_DISP
    VPP_STATUS sts = VPP_DISPLAY_STREAM_Pause(para->videoLayer , para->id);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_STREAM_Pause");
#endif
    return 0;
}

int DisplayStream::delOsd(DispChCtrlPara *para) {
    debug("SVET app: call VPP_DISPLAY_STREAM_Pause({}, {})", para->videoLayer , para->id);
#ifdef VPPSDK_DISP
    VPP_STATUS sts = VPP_DISPLAY_STREAM_Pause(para->videoLayer , para->id);
    CHK_VPPSDK_RET(sts, "VPP_DISPLAY_STREAM_Pause");
#endif
    return 0;
}

int DisplayStream::processControlCmd(DispChCtrlPara *para, VideoPipelineInfo &pipelineInfo) {
    NodeId dispCh;
    dispCh.id = para->id;
    dispCh.type = VPPNodeType::DispCh;
    dispCh.devId = para->videoLayer;

    auto info = pipelineInfo.getNodeInfo(dispCh);
    if (!info) {
        error("SVET app: {} display stream {} with video layer id {} can't be found",
              __func__, dispCh.id, dispCh.devId);
        return SVET_ERR_INVALID_ID;
    }

    DispStreamPara *streamInfo = reinterpret_cast<DispStreamPara *>(info->info.get());
    if (!streamInfo) {
        error("SVET app: {} the display stream with id({}) videoLayer Id({}) can't be found",
            __func__, dispCh.id, dispCh.devId);
        return SVET_ERR_INVALID_ID;
    }

    int res = 0;
    switch (para->cmd) {
        case DispChCtrlCMD::Pause: {
            res = pause(para);
        }
            break;
        case DispChCtrlCMD::Resume: {
            res = resume(para);
        }
            break;

        case DispChCtrlCMD::Hide: {
            res = hide(para);
        }
            break;
        case DispChCtrlCMD::Show: {
            res = show(para);
        }
            break;
        case DispChCtrlCMD::ZoomIn: {
            res = zoomIn(para);
        }
            break;
        case DispChCtrlCMD::ZoomOut: {
            res = zoomOut(para);
        }
            break;
        case DispChCtrlCMD::AddOsd: {
            res = addOsd(para);
        }
            break;
        case DispChCtrlCMD::DelOsd: {
             res = delOsd(para);
        }
            break;

        default: {
            res = SVET_ERR_UNKNOWN_CMD;

            error("SVET app: DisplayStream::processControlCmd Unknown display stream control command type");
        }
            break;

    }
    return res;
}



