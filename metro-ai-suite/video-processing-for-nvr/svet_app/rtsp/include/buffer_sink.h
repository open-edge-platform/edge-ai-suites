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
#include <string>
#include <ctime>
#include <ratio>
#include <chrono>
#include <iostream>
#include <thread>
#include <mutex>
#include <condition_variable>

#include "liveMedia.hh"
#include "BasicUsageEnvironment.hh"


// Define a data sink (a subclass of "MediaSink") to receive the data for each subsession (i.e., each audio or video 'substream').
// In practice, this might be a class (or a chain of classes) that decodes and then renders the incoming audio or video.
// Or it might be a "FileSink", for outputting the received data into a file (as is done by the "openRTSP" application).
// In this example code, however, we define a simple 'dummy' sink that receives incoming data, but does nothing with it.
class BufferSink: public MediaSink
{
public:
    static BufferSink* createNew(UsageEnvironment& env,
                              MediaSubsession& subsession, // identifies the kind of data that's being received
                              char const* streamId = NULL); // identifies the stream itself (optional)

    int readFrameData(char* buffer, unsigned int length);
    virtual Boolean continuePlaying();
    BufferSink(BufferSink const&) = delete;
    BufferSink& operator=(BufferSink const&) = delete;

private:
    BufferSink(UsageEnvironment& env, MediaSubsession& subsession, char const* streamId);
    // called only by "createNew()"
    virtual ~BufferSink();

    static void afterRecvingFrame(void* data, unsigned frameLength,
                                unsigned nTruncatedBytes,
                                struct timeval presentTime,
                                unsigned durationInMicroseconds);
    void afterRecvingFrame(unsigned frameLength, unsigned nTruncatedBytes,
               struct timeval presentTime, unsigned durationInMicroseconds);

private:
    std::mutex mtx;
    MediaSubsession& frameSubsession;
    
    u_int8_t* frameRecvBuf;
    char* frameStreamId;

    int mBufReadOff;
    int mBufReadEnd;
    int mBufReadRewind;
    int mBufWriteOff;
    int mTotalReadSize;
};

// Define a class to hold per-stream state that we maintain throughout each stream's lifetime:
class StreamClientState
{
public:
    StreamClientState();
    virtual ~StreamClientState();

    StreamClientState(StreamClientState const&) = delete;
    StreamClientState& operator=(StreamClientState const&) = delete;
public:
    BufferSink *sink;

    MediaSession* session;
    MediaSubsession* subsession = nullptr;
    MediaSubsessionIterator* iter;

    TaskToken streamTimerTask;
    EventTriggerId continuePlayTrigger;

    double duration;
    time_t start,end;
};


// If you're streaming just a single stream (i.e., just from a single URL, once), then you can define and use just a single
// "StreamClientState" structure, as a global variable in your application.  However, because - in this demo application - we're
// showing how to play multiple streams, concurrently, we can't do that.  Instead, we have to have a separate "StreamClientState"
// structure for each "RTSPClient".  To do this, we subclass "RTSPClient", and add a "StreamClientState" field to the subclass:
class RTSPClientExt: public RTSPClient
{
public:
    static RTSPClientExt* createNew(UsageEnvironment& env, char const* url,
                                  int verbosityLevel = 0,
                                  char const* appName = NULL,
                                  portNumBits tunnelOverHTTPPortNum = 0);

protected:
    RTSPClientExt(UsageEnvironment& env, char const* url,
                int verbosityLevel, char const* appName, portNumBits tunnelOverHTTPPortNum);
    // called only by createNew();
    virtual ~RTSPClientExt();

public:
    StreamClientState scs;
};

extern RTSPClientExt* openURL(char const* url);
extern int start_rtsp_client(void);
extern void closeStream(RTSPClient* client, int exitCode);
