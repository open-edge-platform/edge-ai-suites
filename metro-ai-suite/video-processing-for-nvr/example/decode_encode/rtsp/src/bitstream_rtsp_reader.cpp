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
#include "bitstream_rtsp_reader.h"
#include "buffer_sink.h"

#include <string.h>
#include <assert.h>
#include <chrono>

bool BitstreamRTSPReader::mLive555Initialized = false;
std::thread *BitstreamRTSPReader::mLive555ThreadId = nullptr;

std::atomic<int> BitstreamRTSPReader::sReaderCount{0};
std::mutex BitstreamRTSPReader::sLive555Mutex;
extern void reset_rtsp_daemon_loop();
extern void stop_rtsp_daemon_loop();
extern int requestCloseOnRtspThread(RTSPClient* client);

BitstreamRTSPReader::BitstreamRTSPReader()
    : mClient(nullptr), mSink(nullptr) {
        ++sReaderCount;
}

BitstreamRTSPReader::~BitstreamRTSPReader() {
    Close();

    int left = --sReaderCount;
    fprintf(stderr, "[RTSPDBG] reader dtor, left=%d\n", left);
    fflush(stderr);

    if (left == 0) {
        std::lock_guard<std::mutex> lock(sLive555Mutex);

        fprintf(stderr, "[RTSPDBG] last reader destroyed, stop live555 loop\n");
        fflush(stderr);

        stop_rtsp_daemon_loop();   // Let doEventLoop return

        if (mLive555ThreadId && mLive555ThreadId->joinable()) {
            // Avoid joining itself in extreme cases
            if (std::this_thread::get_id() != mLive555ThreadId->get_id()) {
                mLive555ThreadId->join();
            }
            delete mLive555ThreadId;
            mLive555ThreadId = nullptr;
        }

        mLive555Initialized = false;

        fprintf(stderr, "[RTSPDBG] live555 loop thread joined\n");
        fflush(stderr);
    }
}

// void BitstreamRTSPReader::Close() {
//     if(mClient)
//         closeStream(mClient, 1);
//     printf("SET mClient as nullptr @@@\n");
//     fflush(stdout);
//     mClient = nullptr;
//     mSink = nullptr;
//     mInitialized = false;
// }

void BitstreamRTSPReader::Close() {
    RTSPClientExt* oldClient = mClient;

    if (oldClient) {
        requestCloseOnRtspThread(oldClient);  // No longer closeStream() directly
    }

    mClient = nullptr;
    mSink = nullptr;
    mInitialized = false;
}

void BitstreamRTSPReader::Reset() {
    //RTSP can't reset
    return; 
}

int BitstreamRTSPReader::Open(const char *uri) {
    {
        std::lock_guard<std::mutex> lock(sLive555Mutex);
        if(!mLive555Initialized) {
            reset_rtsp_daemon_loop();
            BitstreamRTSPReader::mLive555ThreadId = new std::thread(start_rtsp_client); //it just have only one live555 scheduler run here 
	        mLive555Initialized = true;
        }
    }
    std::this_thread::sleep_for (std::chrono::milliseconds(100));
    mClient = openURL(uri);
    std::this_thread::sleep_for (std::chrono::milliseconds(100));
    if(!mClient) {
        printf("Open uri failed!\n");
        return -1;
    }

    if (!mClient->scs.session) {
        printf("Open uri failed!\n");
        return -1;
    }

    StreamClientState& scs = ((RTSPClientExt*)mClient)->scs; // alias
    mSink = (BufferSink *)(scs.sink);

    mInitialized = true;

    return 0;
}

/**
 * read bitstreams from RTSP client buffer, if client buffer is empty, it will be blocked
 * until informed that new RTSP packet is received.
 *
 * @param buffer  destnation memory where to store data
 * @param bytesNum How many bytes want to read, nomally it's equal to the size of buffer
 * @return --- actual data bytes if success
 *         --- -1 if not RTSP stream is not connect
 *         --- -2 if RTSP stream is closed
 **/
int BitstreamRTSPReader::Read(char *buffer, size_t bytesNum) {
    UsageEnvironment& env = mClient->envir(); 
    StreamClientState& scs = ((RTSPClientExt*)mClient)->scs;
    if (mSink == NULL) { 
	    printf("RTSP Stream is not connected successfully!\n");
    	return -1;
    }

    int ret = (int)mSink->readFrameData(buffer, bytesNum);

    return ret;
}

void BitstreamRTSPReader::StopEventLoop() {
    std::lock_guard<std::mutex> lock(sLive555Mutex);

    fprintf(stderr, "[RTSPDBG] StopEventLoop begin\n");
    fflush(stderr);

    stop_rtsp_daemon_loop();

    if (mLive555ThreadId && mLive555ThreadId->joinable()) {
        if (std::this_thread::get_id() != mLive555ThreadId->get_id()) {
            mLive555ThreadId->join();
        }
        delete mLive555ThreadId;
        mLive555ThreadId = nullptr;
    }

    mLive555Initialized = false;

    fprintf(stderr, "[RTSPDBG] StopEventLoop done\n");
    fflush(stderr);
}