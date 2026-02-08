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
    class OSD {
    public:
        static int createOSDArea(OSDCtrlPara *para);
        static int attachOSDToStream(OSDCtrlPara *para);
        static int setOSDAreaAttachAttrs(OSDCtrlPara *para);
        static int setOSDAreaAttrs(OSDCtrlPara *para);
        static int validateOSDArea(OSDCtrlPara *para);
        static int detachOSDFromStream(OSDCtrlPara *para);
        static int destroyOSDArea(uint32_t id);
    };
}


