/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2023 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#include <vector>
#include <thread>
#include <atomic>
#include <list>

#include <boost/pool/object_pool.hpp>
#include <boost/pool/pool_alloc.hpp>

#include <grpcpp/grpcpp.h>

#include "common/logger.hpp"
#include "low_latency_server/grpc_server/grpcServer.hpp"
#include "low_latency_server/grpc_server/grpcPipelineManager.hpp"

// protobuf
#include "ai_v1.grpc.pb.h"

#define CONN_POOL_INIT_COUNT 32

#define _AI_INF_CAST_VOIDP_TO_UID(voidp) ((uint16_t)(((reinterpret_cast<std::size_t>(voidp) & UINT32_MAX)>>16)))
#define _AI_INF_CAST_VOIDP_TO_MSG_TYPE(voidp) ((MessageType)(reinterpret_cast<std::size_t>(voidp) & UINT16_MAX))

namespace hce{

namespace ai{

namespace inference{

struct _GrpcCtx{
    hce_ai::ai_inference::AsyncService* service;
    grpc::ServerCompletionQueue* cq;
};

class GrpcServer::Impl{
public:
    class ConnPool{
    public:

        ConnPool(hce_ai::ai_inference::AsyncService* service, grpc::ServerCompletionQueue* cq);

        ~ConnPool() = default;

        ConnPool(const ConnPool& ) = delete;

        ConnPool(ConnPool&& ) = delete;

        ConnPool& operator=(const ConnPool& ) = delete;

        ConnPool& operator=(ConnPool&& ) = delete;

        GrpcServer::Handle create();

        void add(void* tag);

        void remove(GrpcServer::Handle&& handle);

        void remove(void* tag);

        /**
        * @brief return a stored connection handle by its grpc handle
        * 
        * @param tag the grpc handle. handle >> 16 = key
        * @return if tag/key valid, returns the connection. Otherwise an empty shared
        * ptr is returned
        * 
        */
        GrpcServer::Handle get(void* tag);

    private:
        hce_ai::ai_inference::AsyncService* m_service;
        grpc::ServerCompletionQueue* m_cq;

        boost::object_pool<_CommHandle> m_objPool;
        std::unordered_map<uint16_t, Handle, std::hash<uint16_t>, std::equal_to<uint16_t>, 
                boost::fast_pool_allocator<Handle>> m_connections;

        std::atomic<uint16_t> m_ctr;
    };


    Impl();

    ~Impl();

    hceAiStatus_t init(const CommConfig& config);

    hceAiStatus_t start();

    hceAiStatus_t reply(Handle handle, const baseResponseNode::Response& reply);

    hceAiStatus_t replyFinish(Handle handle);

    void stop();

private:
    
    // server state
    enum State{
        Default = 0,
        Initialized,
        Running,
        StopTriggered,
        Stopped
    };    

    void workload();

    CommConfig m_config;
    std::vector<std::thread> m_threads;
    std::atomic<State> m_state;
    std::unique_ptr<ConnPool> m_connPool;

    hce_ai::ai_inference::AsyncService m_service;
    std::unique_ptr<grpc::ServerCompletionQueue> m_cq;
    std::unique_ptr<grpc::Server> m_server;
};

class GrpcServer::_CommHandle:public std::enable_shared_from_this<GrpcServer::_CommHandle>{
public:

    _CommHandle(const _GrpcCtx& grpcCtx, uint16_t uid, GrpcServer::Impl::ConnPool* poolCtx);

    _CommHandle(const _CommHandle&) = delete;

    _CommHandle(_CommHandle&&) = delete;

    _CommHandle& operator=(const _CommHandle&) = delete;

    _CommHandle& operator=(_CommHandle&&) = delete;

    ~_CommHandle();

    void proceed(void* tag, bool ok);

    bool isActive() const;

    uint32_t getTag() const;

    hceAiStatus_t write(const baseResponseNode::Response& reply);

    hceAiStatus_t writeFinish();

private:
    enum MessageType{
        MessageTypeDefault = 0,
        Request,
        Read,
        Write,
        WriteFinish,
        Done
    };

    enum State{
        StateDefault = 0,
        Connected, // rpc started but request has not been received yet. Wait for request
        InProgress, // request has been received and send to pipeline manager. though in future it
                    // can have following up client writes on pause/resume etc. 
                    // wait for follow-up requests and write back results simultaneously
        ServerDone, // pipeline manager indicates no more write to client. Approaching finished
        ConnectionDropped, // client connection dropped when server not indicating finish. A finish with
                           // cancelled status sent
        Finished
    };

    uint32_t getTag(MessageType type) const;


    // to-do: here we assume the system running on is at least 32-bit, otherwise
    // potential bug here due to this uid then shifts 16bit leftward plus state as
    // the tag passed to grpc
    // connection id for each request
    const uint16_t m_uid;

    _GrpcCtx m_grpcCtx;

    // Context for the rpc, allowing to tweak aspects of it such as the use
    // of compression, authentication, as well as to send metadata back to the
    // client.
    grpc::ServerContext m_ctx;

    // What we get from the client.
    hce_ai::AI_Request m_request;
    // What we send back to the client.
    hce_ai::AI_Response m_reply;

    // reply queue for cached messages
    std::list<hce_ai::AI_Response, boost::fast_pool_allocator<hce_ai::AI_Response>> m_replyQueue;
    std::mutex m_replyQueueMutex;


    volatile bool m_writeInProgress; // indicating a write has been fired but haven't received from cq
    std::mutex m_writeMutex;

    // The means to get back to the client.
    grpc::ServerAsyncReaderWriter< ::hce_ai::AI_Response, ::hce_ai::AI_Request> m_responder;

    std::atomic<State> m_state;  // The current serving state.

    GrpcServer::Impl::ConnPool* m_poolCtx;

    /**
    * @brief handle default requests
    * @param tag the grpc handle. handle >> 16 = key
    */
    void mTypeDefault(void* tag) const;

    /**
    * @brief handle RPC requests
    * @param ok ok indicates that the RPC has indeed been started.
    * If it is false, the server has been Shutdown before this particular call got matched to an incoming RPC.
    */
    void mTypeRequest(bool ok);

    /**
    * @brief handle RPC read
    * @param tag the grpc handle. handle >> 16 = key
    * @param ok ok indicates whether there is a valid message that got read.
    * If not, you know that there are certainly no more messages that can ever be read from this stream.
    * For the client-side operations, this only happens because the call is dead.
    * For the server-sider operation, though, this could happen because the client has done a WritesDone already.
    */
    void mTypeRead(void* tag, bool ok);

    /**
    * @brief handle RPC write: ServerCompletionQueue received a message with MessageType::Write
    * @param ok  ok means that the data/metadata/status/etc is going to go to the wire.
    * If it is false, it not going to the wire because the call is already dead (i.e., canceled, deadline expired, other side dropped the channel, etc).
    */
    void mTypeWrite(bool ok);

    /**
    * @brief handle RPC write finish: ServerCompletionQueue received a message with MessageType::WriteFinish
            if the server is at state: ConnectionDropped, this connection need to be removed from connection pool
    * @param tag the grpc handle. handle >> 16 = key
    * @param ok  ok means that the data/metadata/status/etc is going to go to the wire.
    * If it is false, it not going to the wire because the call is already dead (i.e., canceled, deadline expired, other side dropped the channel, etc).
    */
    void mTypeWriteFinish(void* tag, bool ok);

    /**
     * @brief make bad reply for invalid arguments
    */
    void makeBadReqReply();

    /**
     * @brief parse client request, submit tasks to pipeline manager
    */
    void parseClientRequest();
};

GrpcServer::Impl::ConnPool::ConnPool(hce_ai::ai_inference::AsyncService* service, grpc::ServerCompletionQueue* cq):m_ctr(0u), m_objPool(CONN_POOL_INIT_COUNT, 0),
                m_service(service), m_cq(cq){}

GrpcServer::Handle GrpcServer::Impl::ConnPool::create(){
    uint16_t key = m_ctr.fetch_add(1);
    GrpcServer::Handle handle(m_objPool.construct(_GrpcCtx{m_service, m_cq}, key, this), [this](_CommHandle* ptr){ m_objPool.destroy(ptr);});
    _TRC("Add connection with uid {} into the conn pool", key);
    m_connections.emplace(key, handle);
    return handle;
}

void GrpcServer::Impl::ConnPool::remove(GrpcServer::Handle&& handle){
    uint16_t key = (uint16_t)handle->getTag()>>16;
    m_connections.erase(key);
    _TRC("Connection with uid {} removed from conn pool", key);
}

void GrpcServer::Impl::ConnPool::remove(void* tag){
    uint16_t key = _AI_INF_CAST_VOIDP_TO_UID(tag);
    m_connections.erase(key);
    _TRC("Connection with uid {} removed from conn pool", key);
}

GrpcServer::Handle GrpcServer::Impl::ConnPool::get(void* tag){
    uint16_t key = _AI_INF_CAST_VOIDP_TO_UID(tag);
    if(m_connections.find(key) != m_connections.end()){
        return m_connections[key];
    }
    else{
        _ERR("Connection with uid {} cannot be found in conn pool", key);
        std::string output = "";
        for(auto& kv: m_connections) {
            output += std::to_string(kv.first);
        }
        _ERR("{} Connections exist in conn pool: {}", m_connections.size(), output);
        return GrpcServer::Handle();
    }
}

void GrpcServer::Impl::ConnPool::add(void* tag){
    uint16_t key = _AI_INF_CAST_VOIDP_TO_UID(tag);
    GrpcServer::Handle handle(m_objPool.construct(_GrpcCtx{m_service, m_cq}, key, this), [this](_CommHandle* ptr){ m_objPool.destroy(ptr);});
    _TRC("Add new connection with uid {} into the conn pool", key);
    m_connections.emplace(key, handle);
}

GrpcServer::_CommHandle::_CommHandle(const _GrpcCtx& grpcCtx, uint16_t uid, 
        GrpcServer::Impl::ConnPool* poolCtx):m_grpcCtx(grpcCtx), m_responder(&m_ctx), m_state(StateDefault), m_uid(uid),
        m_poolCtx(poolCtx), m_writeInProgress(false){
    _TRC("Connection handle with uid {} created", m_uid);
    uint32_t temp = getTag(Request);
    m_grpcCtx.service->RequestRun(&m_ctx, &m_responder, m_grpcCtx.cq, m_grpcCtx.cq, reinterpret_cast<void*>(temp));
    m_ctx.AsyncNotifyWhenDone(reinterpret_cast<void*>(getTag(Done)));
}

GrpcServer::_CommHandle::~_CommHandle(){
    // _TRC("Connection handle with uid {} destroyed", m_uid);
}

void GrpcServer::_CommHandle::mTypeDefault(void* tag) const {
    _ERR("Invalid message type!");
    m_poolCtx->remove(tag);
}

void GrpcServer::_CommHandle::mTypeRequest(bool ok) {
    HVA_ASSERT(m_state == StateDefault);
    if (ok) {
        // create a new handle for other coming requests
        m_poolCtx->create();
        _TRC("Connection uid {} comes in. State: Default -> Connected", m_uid);
        m_responder.Read(&m_request, reinterpret_cast<void*>(getTag(Read)));
        m_state = Connected;
    } else {
        _WRN("Request on connection with uid {} failed in default state", m_uid);
    }
}


void GrpcServer::_CommHandle::parseClientRequest() {
    
    m_responder.Read(&m_request, reinterpret_cast<void*>(getTag(Read)));
    _TRC("Connection uid {} receives: ", m_uid);
    GrpcPipelineManager::Handle jobHandle = 0;
    std::string pipelineConfig;
    std::vector<std::string> mediaUris;
    unsigned suggestedWeight = 0;
    unsigned streamNum = 1;
    std::string target = "run";
    try {

        for (size_t i = 0; i < m_request.mediauri_size(); i ++) {
            auto mediaUri = m_request.mediauri(i);
            mediaUris.push_back(mediaUri);
        }

        if (m_request.has_target()) {
            target = m_request.target();
        }

        if (m_request.has_suggestedweight()) {
            suggestedWeight = m_request.suggestedweight();
        }

        if (m_request.has_streamnum()) {
            streamNum = m_request.streamnum();
            if (streamNum < 1) {
                throw std::runtime_error("Invalid streamNum, required: > 0!");
            }
        }

        // jobHandle or pipelineConfig: at least one should be provided
        if (m_request.has_jobhandle()) {
            jobHandle = m_request.jobhandle();
        } else {
            if(!m_request.has_pipelineconfig()) {

                _ERR("[GRPC]: Empty pipelineConfig");
                _ERR("[GRPC]: Connection uid {} client request with job handle {} failed!", m_uid, jobHandle);
                makeBadReqReply();
                return;
            }
            pipelineConfig = m_request.pipelineconfig();
            
            // support cross-stream style pipeline config
            if (pipelineConfig.find("stream_placeholder") != std::string::npos) {
                if (target == "run" && mediaUris.size() < streamNum) {
                    throw std::runtime_error("Input mediaUris should be no less than the streamNum!");
                }
                pipelineConfig = std::regex_replace(pipelineConfig, std::regex("stream_placeholder"), std::to_string(streamNum));
            }
            else if (streamNum > 1) {
                _WRN("[GRPC]: pipelineConfig do not contain `stream_placeholder`, request parameter: `streamNum` will not take effect, revert streamNum to 1!");
                streamNum = 1;
            }
        }
    }
    catch (const std::exception &e) {
        _ERR("[GRPC]: Connection with uid {} parsing requests failed: {}", m_uid, e.what());
        makeBadReqReply();
        return;
    }
    catch (...) {
        _ERR("[GRPC]: Connection with uid {} writes finish within Connected state due to read failure", m_uid);
        makeBadReqReply();
        return;
    }
    
    _TRC("Connection uid {} receives request. State change to: InProgress", m_uid);
    m_state = InProgress;

    _TRC("  target: {}", target);
    _TRC("  pipelineConfig: {}", pipelineConfig);
    _TRC("  suggestedWeight: {}", suggestedWeight);
    _TRC("  streamNum: {}", streamNum);
    _TRC("  mediaUris size: {}", mediaUris.size());
    if (target == "load_pipeline") {
        _TRC("[GRPC]: Connection uid {} client load pipeline request submited to pipeline manager", m_uid);
        GrpcPipelineManager::getInstance().submitLoadPipeline(pipelineConfig, shared_from_this(), jobHandle, suggestedWeight, streamNum);
    } else if (target == "unload_pipeline") {
        _TRC("[GRPC]: Connection uid {} client unload pipeline: {} request submited to pipeline manager", m_uid, jobHandle);
        GrpcPipelineManager::getInstance().submitUnloadPipeline(jobHandle, shared_from_this());
    } else if (target == "run") {
        if (mediaUris.size() == 0) {
            _ERR("[GRPC]: Empty media uri");
            _ERR("[GRPC]: Connection uid {} client request with job handle {} failed!", m_uid, jobHandle);
            makeBadReqReply();
            return;
        }
        if (pipelineConfig.empty()){
            _TRC("[GRPC]: Connection uid {} client run pipeline request submited to pipeline manager", m_uid);
            GrpcPipelineManager::getInstance().submitRun(mediaUris, jobHandle, shared_from_this());
        } else {
            _TRC("[GRPC]: Connection uid {} client auto run pipeline request submited to pipeline manager", m_uid);
            GrpcPipelineManager::getInstance().submitAutoRun(mediaUris, pipelineConfig, shared_from_this(), suggestedWeight, streamNum);
            _TRC("[GRPC]: Connection uid {} client auto run pipeline request submited to pipeline manager done!", m_uid);
        }
    } else {
        std::string targetString(target);
        _ERR("[GRPC]: Illegal target {} received!", targetString);
        _ERR("[GRPC]: Connection uid {} client request with job handle {} failed!", m_uid, jobHandle);
        makeBadReqReply();
    }
}


void GrpcServer::_CommHandle::mTypeRead(void* tag, bool ok) {
    if (ok) { // got some request during read
        if (m_state == Connected) {
            _TRC("Connection uid {} Client initial request received", m_uid);
            // parse client requests
            parseClientRequest();
        } else if (m_state == InProgress) {
            _TRC("Connection uid {} runtime message from client comes in", m_uid);
            // parse client requests
            parseClientRequest();
        } else {
            _ERR("Connection uid {} unexpected request received at state {} ", m_uid, m_state);
            // to-do: make some reply
            m_responder.Finish(grpc::Status::CANCELLED, reinterpret_cast<void*>(getTag(Read)));
            m_state = ConnectionDropped;
        }
    } else {
        if (m_state == Connected) {
            _TRC("Client connection dropped without initial request");
            _TRC("Connection with uid {} writes finish within Connected state due to read failure", m_uid);
            makeBadReqReply();
            m_state = ConnectionDropped;
        } else if (m_state == InProgress) {
            _TRC("Client connection dropped during InProgress state");
            _TRC("Connection with uid {} writes finish within Inprogress state due to read failure", m_uid);
            makeBadReqReply();
            m_state = ConnectionDropped;
        } else if (m_state == ServerDone) {
            _TRC("Client connection dropped properly during ServerDone state");
            // we expect finish has been sent in pipeline manager's finish
        } else {
            _ERR("Unexpected request received at state {} ", m_state);
            // to-do: make some reply
            makeBadReqReply();
            m_state = ConnectionDropped;
        }
    }
}

/**
* @brief handle RPC write: ServerCompletionQueue received a message with MessageType::Write
* @param ok  ok means that the data/metadata/status/etc is going to go to the wire.
* If it is false, it not going to the wire because the call is already dead (i.e., canceled, deadline expired, other side dropped the channel, etc).
*/
void GrpcServer::_CommHandle::mTypeWrite(bool ok) {
    if (ok) {
        _TRC("Server write returned with uid {}", m_uid);
        if (m_state == InProgress) {
            std::lock_guard<std::mutex> lg(m_writeMutex);
            // for sanity: the reply messages must have been replied to the client, so that `m_writeInProgress == true` here.
            HVA_ASSERT(m_writeInProgress);
            if (m_replyQueue.empty()) {
                // reset m_writeInProgress, the server is ready for the next reply
                m_writeInProgress = false;
            } else {
                // still have cached rely in m_replyQueue, m_responder should trigger the Write process now
                std::lock_guard<std::mutex> lk(m_replyQueueMutex);
                const auto& toSend = m_replyQueue.front();
                m_responder.Write(toSend, reinterpret_cast<void*>(getTag(Write)));
                m_replyQueue.pop_front();
            }
        } else if (m_state == ServerDone) {
            std::lock_guard<std::mutex> lg(m_writeMutex);
            // for sanity: the reply messages must have been replied to the client, so that `m_writeInProgress == true` here.
            HVA_ASSERT(m_writeInProgress);
            if (m_replyQueue.empty()) {
                _TRC("Connection with uid {} writes finish within ServerDone state", m_uid);
                m_responder.Finish(grpc::Status::OK, reinterpret_cast<void*>(getTag(WriteFinish)));
            } else {
                // still have cached rely in m_replyQueue, m_responder should trigger the Write process now
                std::lock_guard<std::mutex> lk(m_replyQueueMutex);
                const auto& toSend = m_replyQueue.front();
                m_responder.Write(toSend, reinterpret_cast<void*>(getTag(Write)));
                m_replyQueue.pop_front();
            }
        } else {
            _ERR("Write received from cq in error state with uid {}. State is {}", m_uid, m_state);
        }
    } else {
        _ERR("[Write] The call is already dead at state {} ", m_state);
        makeBadReqReply();
        return;
    }
}

/**
* @brief handle RPC write finish: ServerCompletionQueue received a message with MessageType::WriteFinish
            if the server is at state: ConnectionDropped, this connection need to be removed from connection pool
* @param tag the grpc handle. handle >> 16 = key
* @param ok  ok means that the data/metadata/status/etc is going to go to the wire.
* If it is false, it not going to the wire because the call is already dead (i.e., canceled, deadline expired, other side dropped the channel, etc).
*/
void GrpcServer::_CommHandle::mTypeWriteFinish(void* tag, bool ok) {
    if (ok) {
        HVA_ASSERT(m_state == ServerDone || m_state == ConnectionDropped);
        std::lock_guard<std::mutex> lk(m_replyQueueMutex);
        if (!m_replyQueue.empty()) {
            // still have cached rely in m_replyQueue, this is an invalid server state
            _ERR("[WriteFinish] The server is already at state {} while still have cached reply in queue!", m_state);
            m_replyQueue.clear();
        }
        std::lock_guard<std::mutex> lg(m_writeMutex);
        // Ignore all cached replies in m_replyQueue, and reset m_writeInProgress, the server is ready for the next reply
        m_writeInProgress = false;
        _TRC("Write finished received from cq with uid {}", m_uid);
          
        m_poolCtx->remove(tag);
        m_state = Finished;
    } else {
        _ERR("[WriteFinish] The call is already dead at state {} ", m_state);
        return;
    }
}

/**
 * @brief make bad reply for invalid arguments
*/
void GrpcServer::_CommHandle::makeBadReqReply() {
    // {
    //     // server reply to the client immediately
    //     std::lock_guard<std::mutex> lg(m_writeMutex);
    //     m_writeInProgress = true;
    // }
    m_responder.Finish(grpc::Status::CANCELLED, reinterpret_cast<void*>(getTag(WriteFinish)));
}

void GrpcServer::_CommHandle::proceed(void* tag, bool ok){
    HVA_ASSERT(_AI_INF_CAST_VOIDP_TO_UID(tag) == m_uid);

    MessageType mType = (MessageType)_AI_INF_CAST_VOIDP_TO_MSG_TYPE(tag);

    /*
    * in case a proper sequence of communication
    * 0. server calls request method with tag Request
    * 1. client calls the grpc api
    * 2. server's request returned with tag Request
    * 3. server calls read with tag Read to wait for client's argument
    * 4. client writes the argument
    * 5. server's read returned with tag Read
    * 6.1 server calls read with tag Read in case of future runtime requests, e.g. pause/resume
    * 6.2 server parses the arguments, submit to pipeline manager. then it's upto pipeline's choice 
    *     when to make reply
    * 7. in case some reply ready, server calls write with tag Write
    * 8. client reads the server's reply
    * 9. server's write returned with tag Write
    * 10. repeat 7-9 until no more reply
    * 11. server calls finish with tag WriteFinish
    * 12. client's remaining read return with failure
    * 13. server's finish returned with tag WriteFinish

    * in case client drops connection first
    * 0. at some point of above communication
    * 1. client calls writesdone
    * 2. server's read with tag Read returns with failure
    * 3.1 server calls finish with tag WriteFinish
    * 3.2 client calls finish (blocking)
    * 4. server's finish with tag WriteFinish returns
    * 5. client's finish returns
    */
    switch(mType){
        case MessageTypeDefault:
            mTypeDefault(tag);
            break;
        case Request:
            mTypeRequest(ok);
            break;
        case Read:
            mTypeRead(tag, ok);
            break;
        case Write:
            mTypeWrite(ok);
            break;
        case WriteFinish:
            mTypeWriteFinish(tag, ok);
            break;
        case Done:
            _INF("Client request done tag received");
            break;
        default:
            HVA_ASSERT(false);
            break;
    }
}

hceAiStatus_t GrpcServer::_CommHandle::write(const baseResponseNode::Response& reply){
    if(m_state == InProgress){
        hce_ai::AI_Response res;
        res.set_status(hce_ai::AI_Response_Status(reply.status));
        if(!reply.message.empty()){
            res.set_message(reply.message);
        }
        for(const auto& pair: reply.responses){
            hce_ai::Stream_Response sr;
            sr.set_jsonmessages(pair.second.stringData);
            if(!pair.second.binaryData.empty()){
                // sr.set_binary(pair.second.binaryData.get(), pair.second.length);
                sr.set_binary(pair.second.binaryData.c_str(), pair.second.length);
            }
            (*res.mutable_responses())[pair.first] = sr;
        }

        std::lock_guard<std::mutex> lg(m_writeMutex);
        if(!m_writeInProgress){
            _TRC("Connection with uid {} make reply with status {}", m_uid, res.status());
            // Sever can reply messages to client immediately
            m_responder.Write(res, reinterpret_cast<void*>(getTag(Write)));
            m_writeInProgress = true;
        }
        else{
            // indicating a write has been fired but haven't been received from cq, so we cache the new reply in m_replyQueue
            std::lock_guard<std::mutex> lk(m_replyQueueMutex);
            _TRC("Connection with uid {} cached reply with status {}", m_uid, res.status());
            m_replyQueue.push_back(res);
        }
        return hceAiSuccess;
    }
    else if(m_state == ConnectionDropped){
        _WRN("Connection with uid {} failed to reply status {} due to connection dropped", m_uid, reply.status);
        // to-do: possibly to stop the running pipeline to save resource
        return hceAiServiceNotReady;
    }
    else{
        _ERR("Connection with uid {} tried to make reply status {} at wrong state {}", m_uid, reply.status, m_state);
        return hceAiFailure;
    }
}

hceAiStatus_t GrpcServer::_CommHandle::writeFinish(){
    if (m_state == InProgress) {
        std::lock_guard<std::mutex> lg(m_writeMutex);
        if(!m_writeInProgress){
            m_writeInProgress = true;
            _TRC("Connection with uid {} writes finish", m_uid);
            m_state = ServerDone;
            // server reply to the client immediately
            m_responder.Finish(grpc::Status::OK, reinterpret_cast<void*>(getTag(WriteFinish)));
            _TRC("Connection with uid {} done writing finish", m_uid);
        }
        else{
            // server is busy on replying to client, let WriteFinish being sent when m_replyQueue is empty
            m_state = ServerDone;
        }
    }
    else if(m_state == ConnectionDropped){
        _WRN("Connection with uid {} failed to write finish due to connection dropped", m_uid);
        return hceAiServiceNotReady;
    }
    else{
        _ERR("Connection with uid {} tried to write finish at wrong state {}", m_uid, m_state);
        return hceAiFailure;
    }

    return hceAiSuccess;
}

bool GrpcServer::_CommHandle::isActive() const{
    return m_state==InProgress;
}

uint32_t GrpcServer::_CommHandle::getTag() const{
    return ((uint32_t)m_uid)<<16;
}

uint32_t GrpcServer::_CommHandle::getTag(GrpcServer::_CommHandle::MessageType type) const{
    uint32_t temp = type;
    return (((uint32_t)m_uid)<<16) + temp;
}

GrpcServer::Impl::Impl():m_state(Default){

}

GrpcServer::Impl::~Impl(){

}

hceAiStatus_t GrpcServer::Impl::init(const CommConfig& config){
    if(m_state != Default){
        _ERR("Comm Manager is not in correct state during init!");
        return hceAiFailure;
    }
    m_config = config;

    HVA_ASSERT(!m_config.serverAddr.empty());
    std::string server_address(m_config.serverAddr);

    grpc::ServerBuilder builder;
    // Listen on the given address without any authentication mechanism.
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    // Register "service_" as the instance through which we'll communicate with
    // clients. In this case it corresponds to an *asynchronous* service.
    builder.RegisterService(&m_service);
    builder.SetMaxReceiveMessageSize(INT_MAX);
    // builder.SetMaxReceiveMessageSize(-1);
    // Get hold of the completion queue used for the asynchronous communication
    // with the gRPC runtime.
    m_cq = builder.AddCompletionQueue();
    // Finally assemble the server.
    m_server = builder.BuildAndStart();
    _INF("Server set to listen on {}", server_address);
    m_connPool = std::unique_ptr<ConnPool>(new ConnPool(&m_service, m_cq.get()));
    m_state = Initialized;
    return hceAiSuccess;
}

hceAiStatus_t GrpcServer::Impl::start(){
    HVA_ASSERT(m_config.threadPoolSize > 0);
    
    if(m_state != Initialized){
        _ERR("Comm Manager is not in correct state during init!");
        return hceAiFailure;
    }

    m_state = Running;
    m_threads.reserve(m_config.threadPoolSize);
    for(unsigned i = 0; i < m_config.threadPoolSize; ++i){
        m_threads.emplace_back(&GrpcServer::Impl::workload, this);
    }
    _INF("Server starts {} listener. Listening starts", m_config.threadPoolSize);

    return hceAiSuccess;
}

void GrpcServer::Impl::workload(){
    HVA_ASSERT(m_state == Running);
    
    m_connPool->create();

    void* tag;
    bool ok;
    while(m_state == Running){
        if(!m_cq->Next(&tag, &ok)){
            _DBG("Completion queue shuts down");
            // to-do: destruct the conn pool
            break;
        }

        GrpcServer::Handle handle = m_connPool->get(tag);
        if(handle){
            handle->proceed(tag, ok);
        }
        else{
            _ERR("Unspecified tag returned with uid {}", _AI_INF_CAST_VOIDP_TO_UID(tag));
        }

        if(!ok){
            _DBG("Request with uid {} receives non-ok status", _AI_INF_CAST_VOIDP_TO_UID(tag));
            //to-do: add handler according to state
            // m_connPool->remove(tag);
            // break;
            // if (m_state == Running) {
            //     m_connPool->add(tag);
            // }
            // else {
            //     break;
            // }
        }

    };

    _DBG("Listener stops");
}

hceAiStatus_t GrpcServer::Impl::reply(Handle handle, const baseResponseNode::Response& reply){
    return handle->write(reply);
}

hceAiStatus_t GrpcServer::Impl::replyFinish(Handle handle){
    return handle->writeFinish();
}

void GrpcServer::Impl::stop(){
    m_state = StopTriggered;

    m_server->Shutdown();
    for(auto& item: m_threads){
        item.join();
    }
    m_cq->Shutdown();


    m_state = Stopped;
}

GrpcServer::GrpcServer():m_impl(new Impl){

}

GrpcServer::~GrpcServer(){

}

GrpcServer& GrpcServer::getInstance(){
    static GrpcServer inst;
    return inst;
}

hceAiStatus_t GrpcServer::init(const CommConfig& config){
    return m_impl->init(config);
}

hceAiStatus_t GrpcServer::start(){
    return m_impl->start();
}

void GrpcServer::stop(){
    m_impl->stop();
}

hceAiStatus_t GrpcServer::reply(Handle handle, const baseResponseNode::Response& reply){
    return m_impl->reply(handle, reply);
}

hceAiStatus_t GrpcServer::replyFinish(Handle handle){
    return m_impl->replyFinish(handle);
}

}

}

}
