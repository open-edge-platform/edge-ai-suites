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
#ifdef VPPSDK_OSD
#include "vpp_common.h"
#include "vpp_osd.h"
#endif

#include "osd.h"
#include "svet_cmd.h"
#include "svet_util.h"
#include "spdlog/spdlog.h"
#include "video_pipeline.h"

using spdlog::error;
using spdlog::debug;

using namespace SVET_APP;

int OSD::createOSDArea(OSDCtrlPara *para) {
    int res = validateOSDArea(para);
    if (res < 0)
        return res;

    debug("SVET app: {} call VPP_OSD_CreateArea({}, {}, {}, {})", __func__, para->id, para->width, para->height,para->gridSize);
#ifdef VPPSDK_OSD
    VPP_OSD_AreaAttrs attr;
    attr.Type = VPP_OSD_AREATYPE::VPP_OSD_AREATYPE_MOSAIC;
    attr.MosaicAttrs.gridSize = para->gridSize;
    attr.Size.Width = para->width;
    attr.Size.Height = para->height;

    VPP_STATUS sts = VPP_OSD_CreateArea(para->id, &attr);
    return sts;
    //CHK_VPPSDK_RET(sts, "VPP_OSD_CreateArea");
#endif
    return 0;
}

int OSD::attachOSDToStream(OSDCtrlPara *para) {
    // check osd attach to pp or display
    if (para->dispch != -1 && para->videoLayer != -1)
    {
        debug("SVET app: attach to display, {} call VPP_OSD_AttachToStream({}, {}, {}, {}, {})", __func__, para->id, para->dispch, para->videoLayer, para->x, para->y);
#ifdef VPPSDK_OSD
        VPP_StreamIdentifier videoLayerIdentifier;
        videoLayerIdentifier.NodeType = VPP_NODE_TYPE::NODE_TYPE_DISPLAY;
        videoLayerIdentifier.DeviceId = para->videoLayer;
        videoLayerIdentifier.StreamId = para->dispch;
        VPP_OSD_AttachAttr attach_attr;
        attach_attr.MosaicAttrs.Center.X = para->x;
        attach_attr.MosaicAttrs.Center.Y = para->y;

        VPP_STATUS sts = VPP_OSD_AttachToStream(para->id, videoLayerIdentifier, &attach_attr);
        CHK_VPPSDK_RET(sts, "VPP_OSD_AttachToStream");
#endif
    }
    if (para->ppstream != -1)
        {
        debug("SVET app: attach to pp stream, {} call VPP_OSD_AttachToStream({}, {}, {}, {})", __func__, para->id, para->ppstream, para->x, para->y);
#ifdef VPPSDK_OSD
        VPP_StreamIdentifier ppstreamIdentifier;
        ppstreamIdentifier.NodeType = VPP_NODE_TYPE::NODE_TYPE_POSTPROC_STREAM;
        ppstreamIdentifier.DeviceId = VPP_ID_NOT_APPLICABLE;
        ppstreamIdentifier.StreamId = para->ppstream;
        VPP_OSD_AttachAttr attach_attr;
        attach_attr.MosaicAttrs.Center.X = para->x;
        attach_attr.MosaicAttrs.Center.Y = para->y;

        VPP_STATUS sts = VPP_OSD_AttachToStream(para->id, ppstreamIdentifier, &attach_attr);
        CHK_VPPSDK_RET(sts, "VPP_OSD_AttachToStream");
#endif
        }
    return 0;
}

int OSD::setOSDAreaAttachAttrs(OSDCtrlPara *para) {
    // check osd attach to pp or display
    if (para->dispch != -1 && para->videoLayer != -1){
        debug("SVET app: attach to display, {} call VPP_OSD_SetAreaAttachAttrs({}, {}, {}, {}, {})", __func__, para->id, para->dispch, para->videoLayer, para->x, para->y);
#ifdef VPPSDK_OSD
        VPP_StreamIdentifier videoLayerIdentifier;
        videoLayerIdentifier.NodeType = VPP_NODE_TYPE::NODE_TYPE_DISPLAY;
        videoLayerIdentifier.DeviceId = para->videoLayer;
        videoLayerIdentifier.StreamId = para->dispch;
        VPP_OSD_AttachAttr attach_attr;
        attach_attr.MosaicAttrs.Center.X = para->x;
        attach_attr.MosaicAttrs.Center.Y = para->y;

        VPP_STATUS sts = VPP_OSD_SetAreaAttachAttrs(para->id, videoLayerIdentifier, &attach_attr);
        CHK_VPPSDK_RET(sts, "VPP_OSD_SetAreaAttachAttrs");
#endif
    }
    if (para->ppstream != -1)
    {
        debug("SVET app: attach to pp stream, {} call VPP_OSD_SetAreaAttachAttrs({}, {}, {}, {})", __func__, para->id, para->ppstream, para->x, para->y);
#ifdef VPPSDK_OSD
        VPP_StreamIdentifier ppstreamIdentifier;
        ppstreamIdentifier.NodeType = VPP_NODE_TYPE::NODE_TYPE_POSTPROC_STREAM;
        ppstreamIdentifier.DeviceId = VPP_ID_NOT_APPLICABLE;
        ppstreamIdentifier.StreamId = para->ppstream;
        VPP_OSD_AttachAttr attach_attr;
        attach_attr.MosaicAttrs.Center.X = para->x;
        attach_attr.MosaicAttrs.Center.Y = para->y;

        VPP_STATUS sts = VPP_OSD_SetAreaAttachAttrs(para->id, ppstreamIdentifier, &attach_attr);
        CHK_VPPSDK_RET(sts, "VPP_OSD_SetAreaAttachAttrs");
#endif
    }
    return 0;
}

int OSD::setOSDAreaAttrs(OSDCtrlPara *para) {
    int res = validateOSDArea(para);
    if (res < 0)
        return res;

    debug("SVET app: {} call VPP_OSD_SetAreaAttrs({}, {}, {}, {})", __func__, para->id, para->width, para->height,para->gridSize);
#ifdef VPPSDK_OSD
    VPP_OSD_AreaAttrs attr;
    attr.Type = VPP_OSD_AREATYPE::VPP_OSD_AREATYPE_MOSAIC;
    attr.MosaicAttrs.gridSize = para->gridSize;
    attr.Size.Width = para->width;
    attr.Size.Height = para->height;

    VPP_STATUS sts = VPP_OSD_SetAreaAttrs(para->id, &attr);
    CHK_VPPSDK_RET(sts, "VPP_OSD_SetAreaAttrs");
#endif
    return 0;
}

int OSD::detachOSDFromStream(OSDCtrlPara *para) {

    // check osd detach pp or display
    if (para->dispch != -1 && para->videoLayer != -1){
        debug("SVET app: detach display, {} call VPP_OSD_DetachFromStream({}, {}, {})", __func__, para->id, para->dispch, para->videoLayer);
#ifdef VPPSDK_OSD
        VPP_StreamIdentifier videoLayerIdentifier;
        videoLayerIdentifier.NodeType = VPP_NODE_TYPE::NODE_TYPE_DISPLAY;
        videoLayerIdentifier.DeviceId = para->videoLayer;
        videoLayerIdentifier.StreamId = para->dispch;

        VPP_STATUS sts = VPP_OSD_DetachFromStream(para->id, videoLayerIdentifier);
        CHK_VPPSDK_RET(sts, "VPP_OSD_DetachFromStream");
#endif
    }
    if (para->ppstream != -1)
    {
        debug("SVET app: detach to pp stream, {} call VPP_OSD_DetachFromStream({}, {})", __func__, para->id, para->ppstream);
#ifdef VPPSDK_OSD
        VPP_StreamIdentifier ppstreamIdentifier;
        ppstreamIdentifier.NodeType = VPP_NODE_TYPE::NODE_TYPE_POSTPROC_STREAM;
        ppstreamIdentifier.DeviceId = VPP_ID_NOT_APPLICABLE;
        ppstreamIdentifier.StreamId = para->ppstream;

        VPP_STATUS sts = VPP_OSD_DetachFromStream(para->id, ppstreamIdentifier);
        CHK_VPPSDK_RET(sts, "VPP_OSD_DetachFromStream");
#endif
    }
    return 0;
}

int OSD::destroyOSDArea(uint32_t id) {

    debug("SVET app: {} call VPP_OSD_DestroyArea({})", __func__, id);
#ifdef VPPSDK_OSD
    VPP_STATUS sts = VPP_OSD_DestroyArea(id);
    CHK_VPPSDK_RET(sts, "VPP_OSD_DestroyArea");
#endif
    return 0;
}


int OSD::validateOSDArea(OSDCtrlPara *para) {

    if (para->width <= 0 || para->height <= 0 || para->gridSize <= 0 || para->x <=0 || para->y <= 0) {
        error("SVET app: {} invalid OSD Area w={} h={} gridSize={} x={} y={} ", __func__,
                para->width, para->height, para->gridSize, para->x, para->y);
        return SVET_ERR_INVALID_PARA;
    }
    return 0;
}