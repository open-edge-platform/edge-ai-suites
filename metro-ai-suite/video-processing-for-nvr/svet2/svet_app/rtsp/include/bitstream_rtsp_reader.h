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

#ifndef _BIT_STREAM_RTSP_READER__
#define _BIT_STREAM_RTSP_READER__

#include "bitstream_reader.h"
#include <thread>

class RTSPClientExt;
class BufferSink;

class BitstreamRTSPReader : public BitstreamReader {
public :
    BitstreamRTSPReader();
    virtual ~BitstreamRTSPReader();

    virtual int       Open(const char *uri);
    virtual int       Read(char *buffer, size_t bytesNum);
    virtual void      Reset();
    virtual void      Close();
public:
    static bool mLive555Initialized;
    static std::thread *mLive555ThreadId;
private:
    RTSPClientExt *mClient;
    BufferSink *mSink;
};

#endif //_BIT_STREAM_RTSP_READER__
