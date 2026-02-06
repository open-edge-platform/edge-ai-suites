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
#ifdef VPPSDK_PP
#include "vpp_common.h"
#include "vpp_postprocessing.h"
#endif

#include "postprocess.h"
#include "svet_cmd.h"
#include "svet_util.h"
#include "spdlog/spdlog.h"
#include "video_pipeline.h"

using spdlog::error;
using spdlog::debug;

using namespace SVET_APP;

int Postprocess::createPPStream(PostProcessPara *para) {
    int res = validatePPStream(para);
    if (res < 0)
        return res;

    //validatePPStream will return error if output.size < 1
    auto &output = para->OutputParas;

    if (output.size() < 1) {
        error("SVET app: {}: PP must have one output at least", __func__);
        return SVET_ERR_INVALID_PARA;
    }
    debug("SVET app: {} call VPP_POSTPROC_STREAM_Create(id:{}, OutWidth:{] OutHeight:{}, denoise:{}, depth:{}) ",
         __func__, para->id, output[0]->cropW, output[0]->cropH, output[0]->denoise, output[0]->depth);

#ifdef VPPSDK_PP
    VPP_POSTPROC_StreamAttr streamAttr = {0};
    VPP_STATUS sts = VPP_STATUS_SUCCESS;

    streamAttr.CropX = output[0]->cropX;
    streamAttr.CropY = output[0]->cropY;
    streamAttr.CropW = MAX_PP_INPUT_W;
    streamAttr.CropH = MAX_PP_INPUT_H;
    streamAttr.OutHeight = output[0]->cropH;
    streamAttr.OutWidth = output[0]->cropW;
    streamAttr.ColorFormat = VPP_PIXEL_FORMAT_NV12;
    streamAttr.Denoise = output[0]->denoise;
    streamAttr.Depth = 0;
    sts = VPP_POSTPROC_STREAM_Create(para->id, &streamAttr);
    CHK_VPPSDK_RET(sts, "VPP_POSTPROC_STREAM_Create");
#endif
    return 0;

}

int Postprocess::destroyPPStream(PostProcessPara *para) {
    debug("SVET app: {} call VPP_POSTPROC_STREAM_Destroy({}) ", __func__, para->id);
#ifdef VPPSDK_PP
    VPP_POSTPROC_STREAM_Destroy(para->id);
#endif
    return 0;
}

int Postprocess::validatePPStream(PostProcessPara *para) {
    if (para->OutputParas.size() < 1 ) {
        error("SVET app: {} PP stream shall have one output at least", __func__);
        return SVET_ERR_INVALID_PARA;
    }

    auto &outputs = para->OutputParas;

    for (auto &streamout: outputs) {
        if (streamout->cropW == 0 || streamout->cropH == 0 ) {
            error("SVET app: {} invalid output region x={} y={} w={} h={}", __func__,
                  streamout->cropX, streamout->cropY, streamout->cropW, streamout->cropH);
            return SVET_ERR_INVALID_PARA;
        }
    }
    return 0;
}

int Postprocess::stopPPStream(PostProcessPara *para) {
    debug("SVET app: {} call VPP_POSTPROC_STREAM_Stop({}) ", __func__, para->id);
#ifdef VPPSDK_PP
    VPP_STATUS sts = VPP_POSTPROC_STREAM_Stop(para->id);
    CHK_VPPSDK_RET(sts, "VPP_POSTPROC_STREAM_Stop");
#endif
    return 0;
}

int Postprocess::startPPStream(PostProcessPara *para) {
    debug("SVET app: {} call VPP_POSTPROC_STREAM_Start({}) ", __func__, para->id);
#ifdef VPPSDK_PP
    VPP_STATUS sts = VPP_POSTPROC_STREAM_Start(para->id);
    CHK_VPPSDK_RET(sts, "VPP_POSTPROC_STREAM_Start");
#endif
    return 0;
}

int Postprocess::unbindPPStream(PostProcessPara *para) {
    debug("SVET app: {} ", __func__, para->id);
#ifdef VPPSDK_PP
    auto &outputs = para->OutputParas;
    if (outputs.size() ==  1) {
        VPP_StreamIdentifier src;
        src.NodeType = NODE_TYPE_POSTPROC_STREAM;
        src.DeviceId = VPP_ID_NOT_APPLICABLE;
        src.StreamId = para->id;
        VPP_StreamIdentifier sinkStream;
        return VideoPipelineInfo::unbindFromSink(src, sinkStream);
    }

#endif
    return 0;
}
