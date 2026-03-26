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

#pragma once

#include "video_pipeline.h"

namespace SVET_APP {
    class PipelineManager;
    class DisplayStream {
    public:
        DisplayStream();

        static int create(DispStreamPara *para, int fps);
        static int processControlCmd(DispChCtrlPara *para, VideoPipelineInfo &pipelineInfo);

        static int destroy(int streamId, int videoLayerId);
        static int pause(DispChCtrlPara *para);

        static int resume(DispChCtrlPara *para);

        static int hide(DispChCtrlPara *para);

        static int show(DispChCtrlPara *para);

        static int zoomIn(DispChCtrlPara *para);

        static int zoomOut(DispChCtrlPara *para);

        static int addOsd(DispChCtrlPara *para);

        static int delOsd(DispChCtrlPara *para);


    };
}



