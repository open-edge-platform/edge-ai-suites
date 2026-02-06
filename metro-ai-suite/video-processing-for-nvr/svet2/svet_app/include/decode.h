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

#include <thread>
#include <memory>
#include <mutex>
#include <string>
#include <condition_variable>
#include "svet_cmd.h"
#include "svet_util.h"
#include "bitstream_reader.h"
#include "sample_queue.h"
#include "video_pipeline.h"

namespace SVET_APP {
    struct DecodeStateReq
    {
        DecodeStateReq() : reqState(NodeState::Uninitialized) {};
        NodeState reqState;
    };

class Decode {
public:
    using Ptr = std::shared_ptr<Decode>;
    Decode() : mState(NodeState::Uninitialized), mId(-1), mBuf(nullptr),
    mBufSize(1000000), mThread(nullptr), mFrameNum(0), mReachEOF(false), mIsRtsp(false),
    mDumpFile(nullptr), mLoopInput(false) {};

    const unsigned int DECODE_TIMEOUT = 500;
    const unsigned int SENDINPUT_INTERVAL = 20;
    const unsigned int SENDINPUT_RETRY = 20;
    const unsigned int SLEEP_US_AFTER_EOF = 100000;
    const unsigned int SLEEP_US_WAIT_STOP = 10000;
    const unsigned int UNBIND_RETRY_TIMES = 5;

    //If open the bitstream URL fails, init returns error and the decoder state still be Uninitialized.
    //Create the thread if it hasn't been created
    int init(NewDecPara *para);

    //Signal the thread that it can start to send bitstream to VPP SDK decoder.
    int start();

    //Signal the thread that it shall stop sending bitstreams
    int stop();

    //wait for the thread to exit
    int destroy();

    int enableUserPic(int w, int h, bool flagInstant, void *data);
    int disableUserPic();

    int unbindFromSink(NodeId &sinkNode);

    int getId() {return mId;}
    ~Decode();

    static const std::string RTSP_URL_PREFIX;

    Decode(Decode const&) = delete;
    Decode& operator=(Decode const&) = delete;
private:
    void loop();
    int handleStateChangeReq(NodeState reqState, bool &toExit);
    int play();

    SampleQueue<DecodeStateReq> mMsgQueue;

    NodeState mState;
    unsigned long long mFrameNum;

    std::shared_ptr<std::thread> mThread;
    std::shared_ptr<BitstreamReader> mReader;

    int mId;
    char * mBuf;
    std::size_t mBufSize;
    bool mReachEOF;
    bool mIsRtsp;
    bool mLoopInput;

    FILE *mDumpFile;
};
}

