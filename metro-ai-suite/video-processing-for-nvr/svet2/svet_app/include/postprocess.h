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
#include "svet_cmd.h"
#include "video_pipeline.h"

namespace SVET_APP {
    class Postprocess {
    public:
        static int createPPStream(PostProcessPara *para);
        static int destroyPPStream(PostProcessPara *para);
        static int startPPStream(PostProcessPara *para);
        static int stopPPStream(PostProcessPara *para);
        static int validatePPStream(PostProcessPara *para);
        static int unbindPPStream(PostProcessPara *para);
        static const int MAX_PP_INPUT_W = 8192;
        static const int MAX_PP_INPUT_H = 8192;
    };
}


