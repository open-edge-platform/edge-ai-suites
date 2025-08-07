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
//
// Created  on 2022/9/29.
//

#pragma once
#include <string>
#include <fstream>

namespace SVET_APP {
#define SVET_ERR_NONE 0
#define SVET_ERR_INVALID_PIPELINE -1
#define SVET_ERR_INVALID_PARA -2
#define SVET_ERR_INVALID_ID -3
#define SVET_ERR_VPPSDK_FAIL -4
#define SVET_ERR_PIXELFORMMAT_UNSUPPORT -5
#define SVET_ERR_UNKNOWN_CMD -6
#define SVET_ERR_WRONG_STATE -7
#define SVET_ERR_FILE_NOT_EXIST -8
#define SVET_ERR_DUPLICATED_ID -9
#define SVET_ERR_MEMORY_ALLOC_FAIL -9


#define CHK_VPPSDK_RET(sts, func_name) \
do {                        \
    if (sts != VPP_STATUS_SUCCESS)    { \
        error("SVET app: VPPSDK {} return {}", func_name, int(sts)); \
        return (int)sts;      \
    }                         \
} while (0)

struct Rect {
    uint16_t x;
    uint16_t y;
    uint16_t w;
    uint16_t h;
};


enum class NodeState : unsigned int {
    Uninitialized = 0,
    Initialized,
    Play,
    Stop,
    Destroy
};

inline bool isFileGood(const char *filename) {
    std::ifstream file(filename);
    return file.good();
}

}
