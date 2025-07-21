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

#ifndef _BIT_STREAM__READER__
#define _BIT_STREAM__READER__

#include <stddef.h>
#include <stdint.h>

class BitstreamReader {
public :
    BitstreamReader();
    virtual ~BitstreamReader();

    virtual int       Open(const char *fileNameOrUri) = 0;
    virtual int       Read(char *buffer, size_t bytesNum) = 0;
    virtual void      Reset() = 0;
    virtual void      Close() = 0;
protected:
    bool mInitialized;
};

#endif //_BIT_STREAM__READER__
