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
// Even though we're not going to be doing anything with the incoming data, we still need to receive it.
// Define the size of the buffer that we'll use:
#include "buffer_sink.h"


/****** Implementation of "StreamClientState" *********/
StreamClientState::StreamClientState()
  : iter(NULL), session(NULL), subsession(NULL), streamTimerTask(NULL), duration(0.0) ,continuePlayTrigger(0),
  start(0), end(0), sink(nullptr)
{
}

StreamClientState::~StreamClientState()
{
    delete iter;

    if (session != NULL) {
        // We also need to delete "session", and unschedule "streamTimerTask" (if set)
        UsageEnvironment& env = session->envir(); // alias

        env.taskScheduler().unscheduleDelayedTask(streamTimerTask);
        env.taskScheduler().deleteEventTrigger(continuePlayTrigger);
        continuePlayTrigger = 0;
        Medium::close(session);
    }
}

/****** Implementation of "BufferSink" *********/
#define BUFFER_SINK_RECEIVE_BUFFER_SIZE (4000*1024 + 4)
#define BUFFER_SINK_MIN_FREE_SIZE (512*1000)

BufferSink* BufferSink::createNew(UsageEnvironment& env, MediaSubsession& subsession, char const* streamId) 
{
    return new BufferSink(env, subsession, streamId);
}

BufferSink::BufferSink(UsageEnvironment& env, MediaSubsession& subsession, char const* streamId)
  : MediaSink(env),
    frameSubsession(subsession), frameRecvBuf(nullptr), frameStreamId(nullptr), 
    mBufReadOff(0), mBufWriteOff(0), mBufReadEnd(0), mBufReadRewind(0), mTotalReadSize(0)
{
    frameStreamId = strDup(streamId);

    frameRecvBuf = new u_int8_t[BUFFER_SINK_RECEIVE_BUFFER_SIZE];
    //frame start code
    frameRecvBuf[0] = frameRecvBuf[1] = frameRecvBuf[2] = 0x00;
    frameRecvBuf[3] = 0x01;
}

BufferSink::~BufferSink() 
{
    delete[] frameRecvBuf;
    delete[] frameStreamId;
}

void BufferSink::afterRecvingFrame(unsigned frameLength, unsigned nTruncatedBytes,
            struct timeval presentTime, unsigned /*durationInMicroseconds*/) 
{
    std::unique_lock<std::mutex> lock(mtx);

    if (mBufReadRewind < 0) {
        mBufReadRewind = (frameLength + 4);
        //std::cout<<"Rewind from beginning . new read off end "<<mBufReadRewind<<std::endl;
    } else if( mBufReadRewind > 0) {
        mBufReadRewind += (frameLength + 4);
    } else
    {
        mBufReadEnd += (frameLength + 4);
    }
   
    mBufWriteOff += (frameLength + 4);

    if (BUFFER_SINK_RECEIVE_BUFFER_SIZE - mBufWriteOff < BUFFER_SINK_MIN_FREE_SIZE ) {
        mBufWriteOff = 0;
        mBufReadRewind = -1;
    }

    frameRecvBuf[0 + mBufWriteOff] = 0x00;
    frameRecvBuf[1 + mBufWriteOff] = 0x00;
    frameRecvBuf[2 + mBufWriteOff] = 0x00;
    frameRecvBuf[3 + mBufWriteOff] = 0x01;


    continuePlaying();
}

void BufferSink::afterRecvingFrame(void* data, unsigned frameLength, unsigned nTruncatedBytes,
                                  struct timeval presentTime, unsigned durationInMicroseconds) 
{
    BufferSink* sink = (BufferSink*)data;
    sink->afterRecvingFrame(frameLength, nTruncatedBytes, presentTime, durationInMicroseconds);
}

Boolean BufferSink::continuePlaying() 
{
    if (fSource == NULL) return False; // sanity check (should not happen)

    // Request the next frame of data from our input source.  "afterRecvingFrame()" will get called later, when it arrives
    fSource->getNextFrame(frameRecvBuf + mBufWriteOff + 4, BUFFER_SINK_RECEIVE_BUFFER_SIZE,
                        afterRecvingFrame, this,
                        onSourceClosure, this);
    return True;
}

int BufferSink::readFrameData(char* buffer, unsigned int length)
{
    unsigned int copyBytes = 0;
    int count =0;
    char * readoff = (char *)frameRecvBuf;

    if (fSource == NULL) 
        return -1;

    if (length < 10 ) {
        std::cout<<"RTSP received buffer is too small :"<<length<<std::endl;
        return 0;
    }
 
    while ((mBufReadEnd - mBufReadOff) <= 4 && mBufReadRewind <=4 && count++ < 100) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
        if (count >= 100) {
            std::cout <<"SVET app: RTSP readFrameData() wait rtsp timeout!!!!" << std::endl;
            return 0;
        }
    }

    {
        std::unique_lock<std::mutex> lock(mtx);
        if (mBufReadEnd - mBufReadOff > 4) {
            copyBytes =  std::min(length, (unsigned int)(mBufReadEnd - mBufReadOff));
            readoff +=  mBufReadOff;
            mBufReadOff += copyBytes;
        } else if (mBufReadRewind > 4) {
            copyBytes =  std::min(length, (unsigned int)(mBufReadRewind));
            
            mBufReadOff = copyBytes;
            mBufReadEnd = mBufReadRewind;
            mBufReadRewind = 0;
        } else {
          return 0;
        }
    }

    memcpy(buffer, readoff, copyBytes);
    mTotalReadSize += copyBytes;

    return (int)copyBytes;
}

/*********** Implementation of "RTSPClientExt" **************/
RTSPClientExt* RTSPClientExt::createNew(UsageEnvironment& env, char const* url,
                                        int verbosityLevel, char const* appName, portNumBits tunnelOverHTTPPortNum) {
  return new RTSPClientExt(env, url, verbosityLevel, appName, tunnelOverHTTPPortNum);
}

RTSPClientExt::RTSPClientExt(UsageEnvironment& env, char const* url,
                             int verbosityLevel, char const* appName, portNumBits tunnelOverHTTPPortNum)
  : RTSPClient(env, url, verbosityLevel, appName, tunnelOverHTTPPortNum, -1) {
}

RTSPClientExt::~RTSPClientExt() {
}
