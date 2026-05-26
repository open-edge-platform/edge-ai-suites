/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2022 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef HCE_AI_INF_LL_LOW_LATENCY_CLIENT_HPP
#define HCE_AI_INF_LL_LOW_LATENCY_CLIENT_HPP

#include <string>
#include <atomic>
#include <mutex>
#include <vector>
#include <cassert>
#include <iostream>

#include <boost/beast/core.hpp>
#include <boost/beast/http.hpp>
#include <boost/beast/version.hpp>
#include <boost/beast/core/detail/base64.hpp>
#include <boost/asio/connect.hpp>
#include <boost/asio/ip/tcp.hpp>
#include <boost/property_tree/json_parser.hpp>

namespace hce{

namespace ai{

namespace inference{

namespace beast = boost::beast;     // from <boost/beast.hpp>
namespace http = beast::http;       // from <boost/beast/http.hpp>
namespace net = boost::asio;        // from <boost/asio.hpp>
using tcp = net::ip::tcp;           // from <boost/asio/ip/tcp.hpp>

#define HCE_AI_CLIENT_CHECK_RETURN_IF_FAIL(cond, ret) do{if(!(cond)){ std::cerr << #cond << " failed!" << std::endl; return ret;}} while(false);

class LLHttpClient{
public:
    LLHttpClient(const std::string& address, const std::string& port);

    LLHttpClient(const LLHttpClient&&) = delete;

    LLHttpClient(LLHttpClient&& ins) = delete;

    LLHttpClient& operator=(const LLHttpClient& ) = delete;

    LLHttpClient& operator=(LLHttpClient&& ins) = delete;

    ~LLHttpClient();

    bool connect();
    
    /**
     * @brief Submit a pipeline request
     * 
     * @param pipelineConfig the serialized pipeline string in form of json
     * @param mediaUri the media inputs
     * @param retCode
     * @param retBody
     * @param suggestedWeight an integer to indicate the weight of workload. If 0 is specified this will automatically 
     *     set to equal to number of input files
     * @param streamNum: An unsigned integer value to enable cross-stream inference on the workload of the pipeline submitted. 
     *                  default as 1, this would degrade to the default configuration: one pipeline for one stream.
     * 
    */
    bool run(const std::string& pipelineConfig, const std::vector<std::string>& mediaUri, unsigned& retCode, std::string& retBody, unsigned suggestedWeight = 0, unsigned streamNum = 1);

    bool run(uint32_t handle, const std::vector<std::string>& mediaUri, unsigned& retCode, std::string& retBody);

    bool loadPipeline(const std::string& pipelineConfig, unsigned& retCode, std::string& retBody, unsigned suggestedWeight = 0);

    bool unloadPipeline(uint32_t handle, unsigned& retCode, std::string& retBody);

    void shutdown();

    static std::string composeMediaInputWithROI(const std::string& raw, unsigned x = 0, unsigned y = 0, unsigned w = 0, unsigned h = 0);

private:
    enum _state{
        StateDefault,
        StateConnected,
        StateShutdown
    };

    inline bool _validateIP(const std::string& addr) const{
        struct sockaddr_in sa;
        return 0 != inet_pton(AF_INET, addr.c_str(), &(sa.sin_addr));
    };

    std::string m_addr;
    std::string m_port;
    std::atomic<_state> m_state;
    std::mutex m_mtx;

    // http context
    net::io_context m_ioc;
    tcp::resolver m_resolver;
    beast::tcp_stream m_stream;
};

LLHttpClient::LLHttpClient(const std::string& address, const std::string& port): m_state(_state::StateDefault), m_resolver(m_ioc), m_stream(m_ioc){
    assert((_validateIP(address)));
    m_addr = address;
    m_port = port;
}

LLHttpClient::~LLHttpClient(){
    if(m_state.load(std::memory_order_acquire) == _state::StateShutdown){
        shutdown();
    }
}

bool LLHttpClient::connect(){
    auto const results = m_resolver.resolve(m_addr, m_port);
    if(0 == results.size()){
        return false;
    }
    try{
        m_stream.connect(results);
    }
    catch(std::exception const& e)
    {
        std::cerr << "Error: " << e.what() << std::endl;
        return false;
    }
    m_state.store(_state::StateConnected, std::memory_order_release);
    return true;
}

bool LLHttpClient::run(const std::string& pipelineConfig, const std::vector<std::string>& mediaUri, unsigned& retCode, std::string& retBody, unsigned suggestedWeight, unsigned streamNum){
    HCE_AI_CLIENT_CHECK_RETURN_IF_FAIL((!pipelineConfig.empty()), false);
    HCE_AI_CLIENT_CHECK_RETURN_IF_FAIL(mediaUri.size(), false);
    HCE_AI_CLIENT_CHECK_RETURN_IF_FAIL((m_state.load(std::memory_order_acquire) == _state::StateConnected), false);
    
    http::request<http::string_body> req{http::verb::post, "/run", 11};
    req.set(http::field::host, m_addr);
    req.set(http::field::user_agent, BOOST_BEAST_VERSION_STRING);

    boost::property_tree::ptree jsonTree;
    jsonTree.add("pipelineConfig", pipelineConfig);
    jsonTree.add("suggestedWeight", suggestedWeight);
    jsonTree.add("streamNum", streamNum);

    boost::property_tree::ptree medias;
    for(const auto& item: mediaUri){
        boost::property_tree::ptree media;
        media.put("", item);
        medias.push_back(std::make_pair("", media));
    }
    jsonTree.add_child("mediaUri", medias);

    std::stringstream ss;
    boost::property_tree::json_parser::write_json(ss, jsonTree);
    req.body() = ss.str();
    req.prepare_payload();

    beast::flat_buffer buffer;
    http::response<http::string_body> res;

    try{
        std::lock_guard<std::mutex> lg(m_mtx);
        http::write(m_stream, req);
        http::read(m_stream, buffer, res);
    }
    catch(std::exception const& e)
    {
        std::cerr << "Error: " << e.what() << std::endl;
        return false;
    }

    retCode = (unsigned)res.result();
    retBody = res.body();
    return true;
}

bool LLHttpClient::run(uint32_t handle, const std::vector<std::string>& mediaUri, unsigned& retCode, std::string& retBody){
    return false;
}

bool LLHttpClient::loadPipeline(const std::string& pipelineConfig, unsigned& retCode, std::string& retBody, unsigned suggestedWeight){
    return false;
}

bool LLHttpClient::unloadPipeline(uint32_t handle, unsigned& retCode, std::string& retBody){
    return false;
}

void LLHttpClient::shutdown(){
    if(m_state.load(std::memory_order_acquire) == _state::StateConnected){
        try{
            beast::error_code ec;
            m_stream.socket().shutdown(tcp::socket::shutdown_both, ec);

        if(ec && ec != beast::errc::not_connected)
            throw beast::system_error{ec};
        }
        catch(std::exception const& e)
        {
            std::cerr << "Error: " << e.what() << std::endl;
            return;
        }
    }
    m_state.store(_state::StateShutdown, std::memory_order_release);
}

std::string LLHttpClient::composeMediaInputWithROI(const std::string& raw, unsigned x, unsigned y, unsigned w, unsigned h){
    boost::property_tree::ptree jsonTree;
    jsonTree.add("image", raw);

    boost::property_tree::ptree rois;

    boost::property_tree::ptree roi;
    roi.put("", x);
    rois.push_back(std::make_pair("", roi));

    roi.clear();
    roi.put("", y);
    rois.push_back(std::make_pair("", roi));

    roi.clear();
    roi.put("", w);
    rois.push_back(std::make_pair("", roi));

    roi.clear();
    roi.put("", h);
    rois.push_back(std::make_pair("", roi));
    
    jsonTree.add_child("roi", rois);

    std::stringstream ss;
    boost::property_tree::json_parser::write_json(ss, jsonTree);

    return ss.str();
}

}

}

}

#endif //#ifndef HCE_AI_INF_LL_LOW_LATENCY_CLIENT_HPP