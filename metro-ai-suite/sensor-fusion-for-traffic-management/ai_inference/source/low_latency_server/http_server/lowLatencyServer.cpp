/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2023 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#include <uv.h>

#include <boost/pool/object_pool.hpp>
#include <boost/pool/pool_alloc.hpp>
#include <boost/beast/http.hpp>
#include <boost/property_tree/json_parser.hpp>
#include <boost/exception/all.hpp>
#include <boost/beast/core/detail/base64.hpp>

#include <functional>
#include <atomic>
#include <mutex>
#include <unordered_map>
#include <list>

#include "common/logger.hpp"
#include "low_latency_server/http_server/lowLatencyServer.hpp"
#include "low_latency_server/http_server/httpPipelineManager.hpp"

#define DEFAULT_SOCKET_QUEUE_SIZE 128

#define TCP_CLIENT_POOL_CHUNK_COUNT 128
#define INCOMING_MESSAGE_CHUNK_SIZE 65536
#define INCOMING_MESSAGE_CHUNK_COUNT 32
#define WRITE_REQ_POOL_CHUNK_COUNT 32
#define REPLY_MESSAGE_CHUNK_SIZE sizeof(char)
#define REPLY_MESSAGE_CHUNK_COUNT 65536
#define INPUT_FEATURE_CHUNK_SIZE sizeof(int8_t)
#define INPUT_FEATURE_CHUNK_COUNT 512*64*4 // 512-long feature x say, 64 features per req x say 4 requests at a time
#define CLIENT_DES_CHUNK_COUNT 32


namespace hce{

namespace ai{

namespace inference{

struct HttpServerLowLatency::_ClientDes{
    uv_tcp_t* conn;
};

class HttpServerLowLatency::Impl{
public:
    Impl();

    ~Impl();

    hceAiStatus_t init(const std::string& address, unsigned port);

    hceAiStatus_t run();

    void stop();

    hceAiStatus_t reply(ClientDes client, unsigned code, const std::string& reply);

private:
    hceAiStatus_t workload();

    inline bool validateIP(const std::string& addr) const{
        struct sockaddr_in sa;
        return 0 != inet_pton(AF_INET, addr.c_str(), &(sa.sin_addr));
    };

    class _ConnRegistry{
    public:
        _ConnRegistry(){ };

        ~_ConnRegistry(){ };

        void registerConn(uv_tcp_t* conn){
            _TRC("[HTTP]: registering a conn with addr {}", (void*)conn);
            std::lock_guard<std::mutex> lg(m_mutex);
            m_opennedConn[conn] = std::string();
        }

        void unregisterConn(uv_tcp_t* conn){
            _TRC("[HTTP]: unregistering a conn with addr {}", (void*)conn);
            std::lock_guard<std::mutex> lg(m_mutex);
            m_opennedConn.erase(conn);
        }

        bool exist(uv_tcp_t* conn){
            _TRC("[HTTP]: checking a conn with addr {}", (void*)conn);
            std::lock_guard<std::mutex> lg(m_mutex);
            return m_opennedConn.find(conn) != m_opennedConn.end();
        }

        bool appendMsg(uv_tcp_t* conn, const std::string& msg){
            std::lock_guard<std::mutex> lg(m_mutex);
            if(m_opennedConn.find(conn) == m_opennedConn.end()){
                return false;
            }
            std::string prevMsg = m_opennedConn[conn];
            m_opennedConn[conn] = prevMsg + msg;
            return true;
        };

        bool replaceMsg(uv_tcp_t* conn, const std::string& msg){
            std::lock_guard<std::mutex> lg(m_mutex);
            if(m_opennedConn.find(conn) == m_opennedConn.end()){
                return false;
            }
            m_opennedConn[conn] = msg;
            return true;
        };

        bool deleteMsg(uv_tcp_t* conn){
            std::lock_guard<std::mutex> lg(m_mutex);
            if(m_opennedConn.find(conn) == m_opennedConn.end()){
                return false;
            }
            m_opennedConn[conn].clear();
            return true;
        };

        std::string getMsg(uv_tcp_t* conn){
            std::lock_guard<std::mutex> lg(m_mutex);
            if(m_opennedConn.find(conn) == m_opennedConn.end()){
                return std::string();
            }
            return m_opennedConn[conn];
        };

        bool hasMsg(uv_tcp_t* conn){
            std::lock_guard<std::mutex> lg(m_mutex);
            if(m_opennedConn.find(conn) == m_opennedConn.end()){
                return false;
            }
            return !m_opennedConn[conn].empty();
        };

    private:
        std::mutex m_mutex;
        std::unordered_map<uv_tcp_t*, std::string, std::hash<uv_tcp_t*>, std::equal_to<uv_tcp_t*>,
                boost::fast_pool_allocator<std::pair<uv_tcp_t*, std::string>>> m_opennedConn; 
    };

    // server state
    enum State{
        Default = 0,
        Initialized,
        Running,
        StopTriggered,
        Stopped
    };

    typedef struct {
        uv_write_t req;
        uv_buf_t buf;
    } write_req_t;

    #define _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_NAME(func) func##_wrapper

    #define _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_DEF(func,signature,args...) \
        static void _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_NAME(func)signature { \
            Impl* thisPtr = reinterpret_cast<Impl*>(handle->data); \
            thisPtr->func(args);\
        }

    // a few callbacks used in http server
    void onTimeUp(uv_timer_t* handle);
    _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_DEF(onTimeUp, (uv_timer_t* handle), handle);

    void onIncomingMsgBufRequired(uv_handle_t *handle, size_t suggested_size, uv_buf_t *buf);
    _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_DEF(onIncomingMsgBufRequired, (uv_handle_t *handle, size_t suggested_size, uv_buf_t *buf), handle, suggested_size, buf);

    void onConnectionIn(uv_stream_t *handle, int status);
    _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_DEF(onConnectionIn, (uv_stream_t *handle, int status), handle, status);

    void onRead(uv_stream_t *handle, ssize_t nread, const uv_buf_t *buf);
    _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_DEF(onRead, (uv_stream_t *handle, ssize_t nread, const uv_buf_t *buf), handle, nread, buf);

    void onConnectionClose(uv_handle_t* handle);
    _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_DEF(onConnectionClose, (uv_handle_t* handle), handle);

    void onAsyncReply(uv_async_t* handle);
    _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_DEF(onAsyncReply, (uv_async_t* handle), handle);

    void onReplyComplete(uv_write_t* req, int status);
    _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_DEF(onReplyComplete, (uv_write_t* handle, int status), handle, status);

    inline void makeBadReqReply(uv_stream_t* client){
        std::stringstream ss;
        boost::beast::http::response<boost::beast::http::empty_body> res{boost::beast::http::status::bad_request, 11};
        // res.set(boost::beast::http::field::server, 001);
        res.set(boost::beast::http::field::content_type, "text/html");
        res.prepare_payload();
        ss << res;

        std::string replyString = ss.str();
        _TRC("[HTTP]: http reply string as following: {}", replyString);

        write_req_t *req = m_writeReqPool.malloc();
        HCE_AI_ASSERT(req);
        req->req.data = reinterpret_cast<void*>(this);

        unsigned size = replyString.size();
        char* reply = reinterpret_cast<char*>(m_replyMsgPool.ordered_malloc(replyString.size()));//(char*)malloc(size);
        replyString.copy(reply, size);
        req->buf = uv_buf_init(reply, size);
        uv_write((uv_write_t*) req, client, &req->buf, 1, _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_NAME(onReplyComplete));
        _TRC("[HTTP]: Reply string wrote to uv loop");
    };

    inline void makeOkReply(uv_stream_t* client){
        std::stringstream ss;
        boost::beast::http::response<boost::beast::http::empty_body> res{boost::beast::http::status::ok, 11};
        res.prepare_payload();
        ss << res;

        std::string replyString = ss.str();

        write_req_t *req = m_writeReqPool.malloc();
        HCE_AI_ASSERT(req);
        req->req.data = reinterpret_cast<void*>(this);

        unsigned size = replyString.size();
        char* reply = reinterpret_cast<char*>(m_replyMsgPool.ordered_malloc(replyString.size()));//(char*)malloc(size);
        replyString.copy(reply, size);
        req->buf = uv_buf_init(reply, size);
        uv_write((uv_write_t*) req, client, &req->buf, 1, _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_NAME(onReplyComplete));
    };

    inline void makeInternalServerErrorReply(uv_stream_t* client){
        std::stringstream ss;
        boost::beast::http::response<boost::beast::http::empty_body> res{boost::beast::http::status::internal_server_error, 11};
        res.prepare_payload();
        ss << res;

        std::string replyString = ss.str();

        write_req_t *req = m_writeReqPool.malloc();
        HCE_AI_ASSERT(req);
        req->req.data = reinterpret_cast<void*>(this);

        unsigned size = replyString.size();
        char* reply = reinterpret_cast<char*>(m_replyMsgPool.ordered_malloc(replyString.size()));//(char*)malloc(size);
        replyString.copy(reply, size);
        req->buf = uv_buf_init(reply, size);
        uv_write((uv_write_t*) req, client, &req->buf, 1, _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_NAME(onReplyComplete));
    };

    bool healthCheck();

    // http server contexts
    uv_loop_t* m_uvLoop;
    uv_tcp_t m_tcpServer;
    sockaddr_in m_addrIn;
    // uv_idle_t m_idler;
    uv_timer_t m_timer;
    uv_async_t m_asyncReply;

    // config
    std::string m_address;
    unsigned m_port;

    // various memory pools and allocators
    boost::object_pool<uv_tcp_t> m_tcpCleintPool; // allocator for http client structs
    boost::pool<boost::default_user_allocator_new_delete> m_incomingMsgPool; // allocator for http incoming messages
    boost::object_pool<write_req_t> m_writeReqPool; // allocator for http reply write handles
    boost::pool<boost::default_user_allocator_new_delete> m_replyMsgPool; // allocator for reply message
    boost::object_pool<_ClientDes> m_clientDesPool; // allocator for client descriptor
    std::mutex m_clientDesPoolMtx; // as object pool malloc and free can happen concurrently by different threads 
                                   // i.e. malloc at http server thread and free at pipeline manager thread

    std::atomic<State> m_state;

    _ConnRegistry m_openedConn;

    std::list<std::pair<uv_tcp_t*, std::pair<unsigned, std::string>>, 
            boost::fast_pool_allocator<std::pair<uv_tcp_t*, std::pair<unsigned, std::string>>>> m_replyQueue;
    std::mutex m_replyQueueMutex;

    std::atomic<uint64_t> m_watchdogVal;

    std::thread m_thread;
};

HttpServerLowLatency::Impl::Impl():m_state(Default), m_tcpCleintPool(TCP_CLIENT_POOL_CHUNK_COUNT, 0), 
        m_incomingMsgPool(INCOMING_MESSAGE_CHUNK_SIZE, INCOMING_MESSAGE_CHUNK_COUNT, 0), m_writeReqPool(WRITE_REQ_POOL_CHUNK_COUNT, 0),
        m_replyMsgPool(REPLY_MESSAGE_CHUNK_SIZE, REPLY_MESSAGE_CHUNK_COUNT, 0), m_clientDesPool(CLIENT_DES_CHUNK_COUNT, 0),
        m_port(0), m_watchdogVal(0u){
    m_uvLoop = uv_default_loop();
    uv_async_init(m_uvLoop, &m_asyncReply, _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_NAME(onAsyncReply));
    m_asyncReply.data = reinterpret_cast<void*>(this);
    uv_timer_init(m_uvLoop, &m_timer);
    m_timer.data = reinterpret_cast<void*>(this);
    uv_timer_start(&m_timer, _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_NAME(onTimeUp), 10, 10);
    _TRC("[HTTP]: uv loop inited");
}

HttpServerLowLatency::Impl::~Impl(){

}

bool HttpServerLowLatency::Impl::healthCheck(){
    uint64_t watchdogValFromPM = HttpPipelineManager::getInstance().healthCheck();
    uint64_t watchdogValFromHS = 0u;
    do{
        watchdogValFromHS = m_watchdogVal.load(std::memory_order_acquire);
        if(watchdogValFromHS == watchdogValFromPM){
            // suppose k8s will check this every 1 min, while pipeline manager updates this val every 5s
            return false;
        }
    }while(!m_watchdogVal.compare_exchange_weak(watchdogValFromHS, watchdogValFromPM, std::memory_order_acq_rel));
    return true;
}

void HttpServerLowLatency::Impl::onAsyncReply(uv_async_t* handle){
    std::lock_guard<std::mutex> lg(m_replyQueueMutex);
    auto iter = m_replyQueue.begin();
    while(iter != m_replyQueue.end()){
        if(!m_openedConn.exist(iter->first)){
            _TRC("[HTTP]: A queued reply no longer has its client existing");
            iter = m_replyQueue.erase(iter);
            continue;
        }
        _TRC("[HTTP]: make an http reply");

        boost::beast::http::response<boost::beast::http::string_body> res{boost::beast::http::status(iter->second.first), 11}; // 11 = http version 1.1
        res.set(boost::beast::http::field::content_type, "application/json");
        res.body() = iter->second.second;
        res.prepare_payload();
        std::stringstream ss;
        ss << res;

        std::string replyString = ss.str();
        _TRC("[HTTP]: http reply string as following: {}", replyString);

        write_req_t *req = m_writeReqPool.malloc();
        HCE_AI_ASSERT(req);
        req->req.data = reinterpret_cast<void*>(this);

        unsigned size = replyString.size();
        char* reply = reinterpret_cast<char*>(m_replyMsgPool.ordered_malloc(replyString.size()));//(char*)malloc(size);
        HCE_AI_ASSERT(reply);
        replyString.copy(reply, size);
        req->buf = uv_buf_init(reply, size);
        uv_write((uv_write_t*) req, (uv_stream_t*)iter->first, &req->buf, 1, _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_NAME(onReplyComplete));
        _TRC("[HTTP]: Reply string wrote to uv loop");
        iter = m_replyQueue.erase(iter);
    }
}

void HttpServerLowLatency::Impl::onTimeUp(uv_timer_t* handle){
    if(StopTriggered == m_state.load(std::memory_order_consume)){
        uv_timer_stop(handle);
        uv_stop(m_uvLoop);
        m_state = State::Stopped;
    }
}

void HttpServerLowLatency::Impl::onIncomingMsgBufRequired(uv_handle_t *handle, size_t suggested_size, uv_buf_t *buf){
    buf->base = reinterpret_cast<char*>(m_incomingMsgPool.ordered_malloc(INCOMING_MESSAGE_CHUNK_SIZE));
    buf->len = INCOMING_MESSAGE_CHUNK_SIZE;
    memset(buf->base, 0, buf->len);
    _TRC("[HTTP]: Allocate a buffer with size {} in incoming message pool", INCOMING_MESSAGE_CHUNK_SIZE);
}

void HttpServerLowLatency::Impl::onConnectionIn(uv_stream_t *server, int status) {
    if (status < 0) {
        _ERR("New connection error: {}", uv_strerror(status));
        return;
    }

    _TRC("[HTTP]: new connection come in");
    uv_tcp_t* client = m_tcpCleintPool.malloc(); // free at close callback
    HCE_AI_ASSERT(client);
    uv_tcp_init(m_uvLoop, client);
    client->data = reinterpret_cast<void*>(this);
    if (uv_accept(server, (uv_stream_t*) client) == 0) {
        _TRC("[HTTP]: Connection accepted");
        m_openedConn.registerConn(client);
        uv_read_start((uv_stream_t*) client, _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_NAME(onIncomingMsgBufRequired), _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_NAME(onRead));
    }
    else {
        _TRC("[HTTP]: Connection closed before acception");
        uv_close((uv_handle_t*) client, _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_NAME(onConnectionClose));
    }
}

void HttpServerLowLatency::Impl::onRead(uv_stream_t *client, ssize_t nread, const uv_buf_t *buf){
    if (nread > 0) {
         
        std::string reqString(buf->base, buf->len);
        reqString.erase(std::find(reqString.begin(), reqString.end(), '\0'), reqString.end());
        _TRC("[HTTP]: New message coming");
        m_incomingMsgPool.ordered_free(buf->base, buf->len);
        _TRC("[HTTP]: Freed incoming message buffer with length {}", buf->len);
        std::string pendingReqString = m_openedConn.getMsg((uv_tcp_t*)client);
        if(!pendingReqString.empty()){
            // has unfinished message from last read
            std::stringstream tempss;
            tempss << pendingReqString << reqString;
            reqString = tempss.str();
            _TRC("[HTTP]: Append with previous message");
        }

        boost::beast::error_code ec;
        boost::beast::http::request_parser<boost::beast::http::string_body> parser;

        // Set the eager parse option.
        parser.eager(true);

        // The default limit is 1MB for requests and 8MB for responses.
        // If this is set to `boost::none`, then the body limit is disabled.
        parser.body_limit(boost::none);
        
        // Write a buffer sequence to the parser.
        parser.put(boost::asio::buffer(reqString), ec);
        
        /// @brief Check here on ec returns
        // if parse sucess: `Sucess`
        // others: `body limit exceeded`, `bad method`
        if (ec) {
            _ERR("[HTTP]: Request body parse error: {}", ec.message());
            makeBadReqReply(client);
            return;
        }

        /// @brief 
        // parser.is_done(): Returns true if the message is complete.
        if(!parser.is_done()){
            m_openedConn.replaceMsg((uv_tcp_t*)client, reqString);
            _TRC("[HTTP]: Incomplete message. Cached");
            return;
        }

        _TRC("[HTTP]: message to be processed: {}", reqString);

        // valid http request, we delete the cached message
        m_openedConn.deleteMsg((uv_tcp_t*)client);

        boost::beast::http::verb verb = parser.get().method();

        if(verb == boost::beast::http::verb::post){
            std::string reqBodyString = parser.get().body();
            boost::property_tree::ptree ptree;
            std::stringstream ss(reqBodyString);
            try {
                boost::property_tree::read_json(ss, ptree);
            } catch (const boost::property_tree::ptree_error& e){
                _ERR("[HTTP]: Read json message failed: {}", boost::diagnostic_information(e));
                makeBadReqReply(client);
                return;
            } catch (boost::exception& e){
                _ERR("[HTTP]: Unclassified error while parsing json from coming message: {}", boost::diagnostic_information(e));
                makeBadReqReply(client);
                return;
            }

            if (ptree.empty()){
                _ERR("[HTTP]: Request string provided does not contain valid json structure");
                makeBadReqReply(client);
                return;
            }

            auto target = parser.get().target();
            if(target == "/load_pipeline"){
                _TRC("[HTTP]: load_pipeline request received");
                std::string pipelineConfig;
                unsigned suggestedWeight = 0;
                unsigned streamNum = 1;
                try{
                    pipelineConfig = ptree.get<std::string>("pipelineConfig");
                    // support cross-stream style pipeline config
                    if (pipelineConfig.find("stream_placeholder") != std::string::npos) {
                        streamNum = ptree.get<unsigned>("streamNum");
                        if (streamNum < 1) {
                            throw std::runtime_error("Invalid streamNum, required: > 0!");
                        }
                        pipelineConfig = std::regex_replace(pipelineConfig, std::regex("stream_placeholder"), std::to_string(streamNum));
                    }
                    
                    auto optionalSuggestedWeight = ptree.get_optional<unsigned>("suggestedWeight");
                    if(optionalSuggestedWeight){
                        suggestedWeight = optionalSuggestedWeight.get();
                    }
                }
                catch (const boost::property_tree::ptree_bad_path& e) {
                    _ERR("[HTTP]: Parsing failed: {}", e.what());
                    makeBadReqReply(client);
                    return;
                } catch (const boost::property_tree::ptree_bad_data& e) {
                    _ERR("[HTTP]: Parsing failed: {}", e.what());
                    makeBadReqReply(client);
                    return;
                } catch (boost::exception& e) {
                    _ERR("[HTTP]: Unclassified error upon parsing json file: {}", boost::diagnostic_information(e));
                    makeBadReqReply(client);
                    return;
                }
                
                if(pipelineConfig.empty()){
                    _ERR("[HTTP]: Empty pipeline config");
                    makeBadReqReply(client);
                    return;
                }

                _ClientDes* tempDes;
                {
                    std::lock_guard<std::mutex> lg(m_clientDesPoolMtx);
                    tempDes = m_clientDesPool.malloc();
                }
                ClientDes desc(tempDes, [this](_ClientDes* ptr){ std::lock_guard<std::mutex> lg(m_clientDesPoolMtx); m_clientDesPool.free(ptr);});
                HCE_AI_ASSERT(desc);
                desc->conn = (uv_tcp_t*)client;
                HttpPipelineManager::Handle jobHandle;
                HttpPipelineManager::getInstance().submitLoadPipeline(pipelineConfig, desc, jobHandle, suggestedWeight, streamNum);
                _TRC("[HTTP]: load pipeline req with job handle {} submited to pipeline manager", jobHandle);
            }
            else if(target == "/unload_pipeline"){
                _TRC("[HTTP]: unload_pipeline request received");
                HttpPipelineManager::Handle jobHandle;
                try{
                    jobHandle = ptree.get<uint32_t>("handle");
                }
                catch (const boost::property_tree::ptree_bad_path& e) {
                    _ERR("[HTTP]: Parsing failed: {}", e.what());
                    makeBadReqReply(client);
                    return;
                } catch (const boost::property_tree::ptree_bad_data& e) {
                    _ERR("[HTTP]: Parsing failed: {}", e.what());
                    makeBadReqReply(client);
                    return;
                } catch (boost::exception& e) {
                    _ERR("[HTTP]: Unclassified error upon parsing json file: {}", boost::diagnostic_information(e));
                    makeBadReqReply(client);
                    return;
                }

                _ClientDes* tempDes;
                {
                    std::lock_guard<std::mutex> lg(m_clientDesPoolMtx);
                    tempDes = m_clientDesPool.malloc();
                    HCE_AI_ASSERT(tempDes);
                }
                ClientDes desc(tempDes, [this](_ClientDes* ptr){ std::lock_guard<std::mutex> lg(m_clientDesPoolMtx); m_clientDesPool.free(ptr);});
                HCE_AI_ASSERT(desc);
                desc->conn = (uv_tcp_t*)client;
                HttpPipelineManager::getInstance().submitUnloadPipeline(jobHandle, desc);
                _TRC("[HTTP]: unload pipeline req with job handle {} submited to pipeline manager", jobHandle);
            }
            else if(target == "/run"){
                _TRC("[HTTP]: run request received");
                HttpPipelineManager::Handle jobHandle = 0;
                std::string pipelineConfig;
                std::vector<std::string> mediaUris;
                unsigned suggestedWeight = 0;
                unsigned streamNum = 1;
                try{
                    for(const auto& item: ptree.get_child("mediaUri")){
                        mediaUris.push_back(item.second.data());
                    }

                    auto optionalSuggestedWeight = ptree.get_optional<unsigned>("suggestedWeight");
                    if(optionalSuggestedWeight){
                        suggestedWeight = optionalSuggestedWeight.get();
                    }

                    auto optionalStreamNum = ptree.get_optional<unsigned>("streamNum");
                    if(optionalStreamNum){
                        streamNum = optionalStreamNum.get();
                        if (streamNum < 1) {
                            throw std::runtime_error("Invalid streamNum, required: > 0!");
                        }
                    }

                    auto optionalJobHandle = ptree.get_optional<uint32_t>("handle");
                    if(optionalJobHandle){
                        jobHandle = optionalJobHandle.get();
                    }
                    else{
                        pipelineConfig = ptree.get<std::string>("pipelineConfig");
                        
                        // support cross-stream style pipeline config
                        if (pipelineConfig.find("stream_placeholder") != std::string::npos) {
                            if (mediaUris.size() < streamNum) {
                                throw std::runtime_error("Input mediaUris should be no less than the streamNum!");
                            }
                            pipelineConfig = std::regex_replace(pipelineConfig, std::regex("stream_placeholder"), std::to_string(streamNum));
                        }
                        else if (streamNum > 1) {
                            _WRN("[HTTP]: pipelineConfig do not contain `stream_placeholder`, request parameter: `streamNum` will not take effect, revert streamNum to 1!");
                            streamNum = 1;
                        }
                    }
                }
                catch (const boost::property_tree::ptree_bad_path& e) {
                    _ERR("[HTTP]: Parsing failed: {}", e.what());
                    makeBadReqReply(client);
                    return;
                } catch (const boost::property_tree::ptree_bad_data& e) {
                    _ERR("[HTTP]: Parsing failed: {}", e.what());
                    makeBadReqReply(client);
                    return;
                } catch (boost::exception& e) {
                    _ERR("[HTTP]: Unclassified error upon parsing json file: {}", boost::diagnostic_information(e));
                    makeBadReqReply(client);
                    return;
                }

                if(mediaUris.size() == 0){
                    _ERR("[HTTP]: Empty media uri");
                    makeBadReqReply(client);
                    return;
                }

                _ClientDes* tempDes;
                {
                    std::lock_guard<std::mutex> lg(m_clientDesPoolMtx);
                    tempDes = m_clientDesPool.malloc();
                    HCE_AI_ASSERT(tempDes);
                }
                ClientDes desc(tempDes, [this](_ClientDes* ptr){ std::lock_guard<std::mutex> lg(m_clientDesPoolMtx); m_clientDesPool.free(ptr);});
                desc->conn = (uv_tcp_t*)client;
                if(pipelineConfig.empty()){
                    HttpPipelineManager::getInstance().submitRun(mediaUris, jobHandle, desc);
                    _TRC("[HTTP]: run pipeline req with job handle {} submited to pipeline manager", jobHandle);
                }
                else{
                    HttpPipelineManager::getInstance().submitAutoRun(mediaUris, pipelineConfig, desc, suggestedWeight, streamNum);
                    _TRC("[HTTP]: auto run pipeline req with job handle submited to pipeline manager");
                }
                
            }
            else{
                std::string targetString(target);
                _ERR("[HTTP]: Illegal target {} received!", targetString);
                makeBadReqReply(client);
                return;
            }
        }
        else if(verb == boost::beast::http::verb::get){
            auto target = parser.get().target();
            if(target == "/healthz"){
                _TRC("[HTTP]: health check request received");
                if(healthCheck()){
                    makeOkReply(client);
                }
                else{
                    _ERR("[HTTP]: health check failed!");
                    makeInternalServerErrorReply(client);
                }
            }
            else{
                std::string targetString(target);
                _ERR("[HTTP]: Illegal target {} received!", targetString);
                makeBadReqReply(client);
                return;
            }
        }
        else{
            std::string verbString(boost::beast::http::to_string(verb));
            _ERR("[HTTP]: Illegal verb {} received!", verbString);
            makeBadReqReply(client);
            return;
        }
        return;
    }
    else{
        if(buf->base && buf->len > 0){
            m_incomingMsgPool.ordered_free(buf->base, buf->len);
            _TRC("[HTTP]: freed a buffer with len {} under nread <= 0", buf->len);
        }
        _TRC("[HTTP]: under nread <= 0 comes a buf with len {}", buf->len);
    }
    if (nread < 0) {
        if (nread != UV_EOF){
            _ERR("[HTTP]: uv read error: {}", uv_err_name(nread));
        }
        uv_close((uv_handle_t*) client, _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_NAME(onConnectionClose));
    }
}

void HttpServerLowLatency::Impl::onConnectionClose(uv_handle_t* handle){
    uv_tcp_t* tmp = reinterpret_cast<uv_tcp_t*>(handle);
    m_openedConn.unregisterConn(tmp);
    m_tcpCleintPool.free(reinterpret_cast<uv_tcp_t*>(tmp));
    _TRC("[HTTP]: Connection closed");
}

void HttpServerLowLatency::Impl::onReplyComplete(uv_write_t* req, int status){
    if (status) {
        _ERR("[HTTP]: Write error: {}", uv_strerror(status));
    }
    write_req_t *wr = (write_req_t*) req;
    _TRC("[HTTP]: a message with following contents completed: {}", std::string(wr->buf.base, wr->buf.len));
    m_replyMsgPool.ordered_free(wr->buf.base, wr->buf.len);
    m_writeReqPool.free(wr);
    _TRC("[HTTP]: Freed a write request and reply message pool buffer");
}

hceAiStatus_t HttpServerLowLatency::Impl::init(const std::string& address, unsigned port){
    HCE_AI_CHECK_RETURN_IF_FAIL(State::Default == m_state, hceAiInvalidCall);
    HCE_AI_CHECK_RETURN_IF_FAIL(validateIP(address), hceAiBadArgument);
    HCE_AI_CHECK_RETURN_IF_FAIL(port<=65536, hceAiBadArgument);

    m_address = address;
    m_port = port;

    m_state.store(State::Initialized, std::memory_order_release);

    _TRC("[HTTP]: Init completed");

    return hceAiSuccess;
}

hceAiStatus_t HttpServerLowLatency::Impl::run(){
    HCE_AI_CHECK_RETURN_IF_FAIL(State::Initialized == m_state, hceAiInvalidCall);

    m_thread = std::thread(&HttpServerLowLatency::Impl::workload, this);

    return hceAiSuccess;
}

hceAiStatus_t HttpServerLowLatency::Impl::workload(){
    _TRC("[HTTP]: http server at {}:{}", m_address, m_port);
    uv_tcp_init(m_uvLoop, &m_tcpServer);
    m_tcpServer.data = reinterpret_cast<void*>(this);
    uv_ip4_addr(m_address.c_str(), m_port, &m_addrIn);
    uv_tcp_bind(&m_tcpServer, (const struct sockaddr*)&m_addrIn, 0);

    _TRC("[HTTP]: running starts");
    int r = uv_listen((uv_stream_t*) &m_tcpServer, DEFAULT_SOCKET_QUEUE_SIZE, _HCE_AI_LL_HTTP_SERVER_CALLBACK_WRAPPER_NAME(onConnectionIn));
    if (r) {
        _ERR("[HTTP]: Listen error: {}", uv_strerror(r));
        return hceAiSocketListenFailure;
    }

    m_state.store(State::Running, std::memory_order_release);
    if(0 == uv_run(m_uvLoop, UV_RUN_DEFAULT)){
        return hceAiHttpServerStopByIdle;
    }
    else{
        return hceAiHttpServerStopByExternal;
    }
}

void HttpServerLowLatency::Impl::stop(){
    State expected = State::Running;
    m_state.compare_exchange_strong(expected, State::StopTriggered, std::memory_order_acq_rel);
    m_thread.join();
    _TRC("[HTTP]: stopped");
}

hceAiStatus_t HttpServerLowLatency::Impl::reply(ClientDes client, unsigned code, const std::string& reply){
    HCE_AI_CHECK_RETURN_IF_FAIL(m_openedConn.exist(client->conn), hceAiBadArgument);

    _TRC("[HTTP]: Adding a reply message with code {} to reply queue", code);
    {
        std::lock_guard<std::mutex> lg(m_replyQueueMutex);
        m_replyQueue.emplace_back(client->conn, std::make_pair(code, reply));
    }
    uv_async_send(&m_asyncReply);
    return hceAiSuccess;
}

HttpServerLowLatency::HttpServerLowLatency():m_impl(new Impl){

}

HttpServerLowLatency::~HttpServerLowLatency(){ }

HttpServerLowLatency& HttpServerLowLatency::getInstance(){
    static HttpServerLowLatency inst;
    return inst;
}

hceAiStatus_t HttpServerLowLatency::init(const std::string& address, unsigned port){
    return m_impl->init(address, port);
}

hceAiStatus_t HttpServerLowLatency::run(){
    return m_impl->run();
}

void HttpServerLowLatency::stop(){
    m_impl->stop();
}

hceAiStatus_t HttpServerLowLatency::reply(ClientDes client, unsigned code, const std::string& reply){
    return m_impl->reply(client, code, reply);
}


}

}

}
