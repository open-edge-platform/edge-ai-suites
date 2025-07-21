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
#include "buffer_sink.h"

#include "liveMedia.hh"
#include "BasicUsageEnvironment.hh"
#include "EpollTaskScheduler/EpollTaskScheduler.hh"
#include <string>
#include <ctime>
#include <ratio>
#include <chrono>
#include <iostream>
#include <thread>
#include <mutex>

/************ Macro Definition ************/
#define VERBOSITY_LEVEL 1
// By default, we request that the server stream its data using RTP/UDP.
// If, instead, you want to request that the server stream via RTP-over-TCP, change the following to True:
//#define REQUEST_STREAMING_OVER_TCP False
#define REQUEST_STREAMING_OVER_TCP True


/************* Global Variables ************/
// static variable
static TaskScheduler* taskScheduler = nullptr;
static UsageEnvironment* env = nullptr;

using namespace std::chrono;
std::mutex start_mutex;
char watchVariable = 0;


/************* Function Declaration ************/
void configNextSubsession(RTSPClient* client);
void streamEventTrigger(void* data);

// RTSP response handlers
void processEndOfDescribe(RTSPClient* client, int describeRetCode, char* describeRetString);
void processEndOfSetup(RTSPClient* client, int setupRetCode, char* setupRetString);
void processEndOfPlay(RTSPClient* client, int playRetCode, char* playRetString);

// Other event handlers
void subsessionEndOfPlaying(void* data);
void subsessionEndHandler(void* data, char const* reason);
void streamTimerHandler(void* data);

// Used to close a stream (including its "RTSPClient" object):
RTSPClientExt* openURL(UsageEnvironment& env, char const* progName, char const* url);
void closeStream(RTSPClient* client, int exitCode = 1);


/************* Function Implementation ************/
// A function that outputs a string that identifies each stream (for debugging output). 
UsageEnvironment& operator<<(UsageEnvironment& usageEnv, const RTSPClient& client) {
    return usageEnv << "[URL:\"" << client.url() << "\"]: ";
}

UsageEnvironment& operator<<(UsageEnvironment& usageEnv, const MediaSubsession& session) {
    return usageEnv << session.mediumName() << "/" << session.codecName();
}

void streamEventTrigger(void* data) 
{
    RTSPClientExt* client = (RTSPClientExt*)data;

    StreamClientState& clientState = client->scs;
    BufferSink *sink = (BufferSink *)(clientState.sink);
    sink->continuePlaying();
}

void subsessionEndOfPlaying(void* data)
{
    MediaSubsession* subsession = (MediaSubsession*)data;
    MediaSession& session = subsession->parentSession();
    MediaSubsessionIterator iter(session);
    RTSPClient* client = (RTSPClient*)(subsession->miscPtr);

    if (subsession->sink != NULL)
        Medium::close(subsession->sink);
    subsession->sink = NULL;

    while ((subsession = iter.next()) != NULL) {
        if (subsession->sink != NULL)
            return;
    }

    std::cout << "subsessionEndOfPlaying entered\n";
    closeStream(client);
}

void subsessionEndHandler(void* data, char const* reason) 
{
    MediaSubsession* subsession = (MediaSubsession*)data;
    RTSPClient* client = (RTSPClient*)subsession->miscPtr;
    UsageEnvironment& env = client->envir();

    if (reason != NULL) {
        env << " (reason:\"" << reason << "\")";
        delete[] (char*)reason;
    }

    subsessionEndOfPlaying(subsession);
}

void streamTimerHandler(void* data)
{
    RTSPClientExt* client = (RTSPClientExt*)data;
    StreamClientState& clientState = client->scs;

    clientState.streamTimerTask = NULL;

    std::cout << "streamTimerHandler called\n";
    closeStream(client);
}

void closeStream(RTSPClient* client, int exitCode) 
{
    UsageEnvironment& env = client->envir();
    StreamClientState& clientState = ((RTSPClientExt*)client)->scs;

    if (clientState.session != NULL) { 
        Boolean sessionStillActive = False;
        MediaSubsessionIterator iter(*clientState.session);
        MediaSubsession* session;

        while ((session = iter.next()) != NULL) {
            if (session->sink != NULL) {
	        Medium::close(session->sink);
	        session->sink = NULL;

	        if (session->rtcpInstance() != NULL) {
                    session->rtcpInstance()->setByeHandler(NULL, NULL); 
	        }

	        sessionStillActive = True;
            }
        }

        if (sessionStillActive) {
            client->sendTeardownCommand(*clientState.session, NULL);
        }
    }

    // TODO: why it's commented
    //Medium::close(client);
}

void configNextSubsession(RTSPClient* client) 
{
    UsageEnvironment& env = client->envir();
    StreamClientState& clientState = ((RTSPClientExt*)client)->scs;
  
    clientState.subsession = clientState.iter->next();
    if (clientState.subsession != NULL) {
        if (!clientState.subsession->initiate()) {
            env << *client << "Failed to initiate the \"" << *clientState.subsession << "\" subsession: " << env.getResultMsg() << "\n";
            configNextSubsession(client); // give up on this subsession; go to the next one
        } else {
            env << *client << "Initiated the \"" << *clientState.subsession << "\" subsession (";
            if (clientState.subsession->rtcpIsMuxed()) {
	        env << "client port " << clientState.subsession->clientPortNum();
            } else {
	        env << "client ports " << clientState.subsession->clientPortNum() << "-" << clientState.subsession->clientPortNum()+1;
            }
            env << ")\n";

            client->sendSetupCommand(*clientState.subsession, processEndOfSetup, False, REQUEST_STREAMING_OVER_TCP);
        }
        return;
    }

    if (clientState.session->absStartTime() != NULL) {
        client->sendPlayCommand(*clientState.session, processEndOfPlay, clientState.session->absStartTime(), clientState.session->absEndTime());
    } else {
        clientState.duration = clientState.session->playEndTime() - clientState.session->playStartTime();
        client->sendPlayCommand(*clientState.session, processEndOfPlay);
    }
}

// Implementation of the RTSP 'response handlers':
void processEndOfDescribe(RTSPClient* client, int resultCode, char* resultString) 
{
    char* const sdpDesc = resultString;
    UsageEnvironment& env = client->envir();
    StreamClientState& clientState = ((RTSPClientExt*)client)->scs;

    if (resultCode != 0) {
        env << *client << "Failed to get a SDP description: " << resultString << "\n";
        delete[] resultString;
        goto exit;
    }

    env << *client << "Got a SDP description:\n" << sdpDesc << "\n";

    clientState.session = MediaSession::createNew(env, sdpDesc);
    delete[] sdpDesc;

    if (clientState.session == NULL) {
       env << *client << "Failed to create a MediaSession object from the SDP description: " << env.getResultMsg() << "\n";
       goto exit;
    } else if (!clientState.session->hasSubsessions()) {
       env << *client << "This session has no media subsessions (i.e., no \"m=\" lines)\n";
       goto exit;
    }

    clientState.iter = new MediaSubsessionIterator(*clientState.session);
    configNextSubsession(client);

    return;

exit:
    closeStream(client);
}

void processEndOfSetup(RTSPClient* client, int setupRetCode, char* setupRetString)
{
    static int streamCount = 0;
    char fileName[256];
    UsageEnvironment& env = client->envir();
    StreamClientState& clientState = ((RTSPClientExt*)client)->scs;

    if (0 != setupRetCode) {
        env << *client << "Error to set up \"" << *clientState.subsession << "\" subsession: " << setupRetString << "\n";
        goto exit;
    }

    env << *client << "Setup the \"" << *clientState.subsession << "\" subsession (";
    if (clientState.subsession->rtcpIsMuxed()) {
        env << "client port " << clientState.subsession->clientPortNum();
    } else {
        env << "client ports " << clientState.subsession->clientPortNum() << "-" << clientState.subsession->clientPortNum()+1;
    }
    env << ")\n";
       
    sprintf(fileName, "tcl_test_file_sink%d", streamCount++);
    clientState.sink =  BufferSink::createNew(env, *clientState.subsession, fileName);
    clientState.subsession->sink = clientState.sink;
    if (clientState.subsession->sink == NULL) {
        env << *client << "Error to create a data sink for subsession \"" << *clientState.subsession
            << "\" : " << env.getResultMsg() << "\n";
        goto exit;
    }

    env << *client << "Created data sink for subsession \"" << *clientState.subsession << "\" \n";
    clientState.subsession->miscPtr = client; // a hack to let subsession handler functions get the "RTSPClient" from the subsession 
    time(&clientState.start);

    clientState.subsession->sink->startPlaying(*(clientState.subsession->readSource()),
	       subsessionEndOfPlaying, clientState.subsession);

    if (NULL != clientState.subsession->rtcpInstance()) {
        clientState.subsession->rtcpInstance()->setByeWithReasonHandler(subsessionEndHandler, clientState.subsession);
    }

exit:
    delete[] setupRetString;
    configNextSubsession(client);
}

void processEndOfPlay(RTSPClient* client, int playRetCode, char* playRetString) {
    Boolean isSuccess = False;
    UsageEnvironment& env = client->envir();
    StreamClientState& clientState = ((RTSPClientExt*)client)->scs;

    if (playRetCode != 0) {
        env << *client << "Error to start playing session: " << playRetString << "\n";
        goto exit;
    }

    if (clientState.duration > 0) {
        unsigned const delay = 2; 
	clientState.duration += delay;

        unsigned uSecsToDelay = (unsigned)(clientState.duration*1000000);
        clientState.streamTimerTask = env.taskScheduler().scheduleDelayedTask(uSecsToDelay, (TaskFunc*)streamTimerHandler, client);
    }

    env << *client << "Started playing session";
    if (clientState.duration > 0) {
        env << " (for up to " << clientState.duration << " seconds)";
    }
    env << "...\n";

    isSuccess = True;
   
exit:
    delete[] playRetString;

    if (!isSuccess) {
        closeStream(client);
    }
}

int start_rtsp_client(void) 
{
    {
	std::unique_lock<std::mutex> lock(start_mutex);
	if (taskScheduler)
	    return 0;

        std::cout << "create rtsp client env & task scheduler\n";
        taskScheduler = EpollTaskScheduler::createNew();
        env = BasicUsageEnvironment::createNew(*taskScheduler);
    }

    std::cout << "start rtsp event loop\n";
    env->taskScheduler().doEventLoop(&watchVariable);

    env->reclaim(); 
    env = nullptr;
   
    delete taskScheduler; 
    taskScheduler = nullptr;  

    return 0;
}

RTSPClientExt* openURL(char const* url) 
{
    if(env == NULL)
	return nullptr;

    RTSPClientExt* client = RTSPClientExt::createNew(*env, url, VERBOSITY_LEVEL, url);
    if (client == NULL) {
        return nullptr;
    }

    client->sendDescribeCommand(processEndOfDescribe); 

    StreamClientState& clientState = client->scs;
    clientState.continuePlayTrigger = env->taskScheduler().createEventTrigger((TaskFunc*)streamEventTrigger);

    return client;
}
