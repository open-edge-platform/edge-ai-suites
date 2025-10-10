/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2025 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef HCE_AI_INF_GRPC_CLIENT_HPP
#define HCE_AI_INF_GRPC_CLIENT_HPP

#include <iostream>
#include <memory>
#include <string>
#include <fstream>
#include "inc/util/hvaUtil.hpp"

#include <boost/beast/http.hpp>

#include <grpcpp/grpcpp.h>

#include "ai_v1.grpc.pb.h"

namespace hce{

namespace ai{

namespace inference{

#define HCE_AI_CLIENT_CHECK_RETURN_IF_FAIL(cond, ret) do{if(!(cond)){ std::cerr << #cond << " failed!" << std::endl; return ret;}} while(false);

class GRPCClient {
public:
    GRPCClient(const std::string& address, const std::string& port);

    GRPCClient(const GRPCClient&&) = delete;

    GRPCClient(GRPCClient&& ins) = delete;

    GRPCClient& operator=(const GRPCClient& ) = delete;

    GRPCClient& operator=(GRPCClient&& ins) = delete;

    ~GRPCClient();

    std::shared_ptr<hce_ai::ai_inference::Stub> connect();

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

    std::shared_ptr<
        grpc::ClientReaderWriter<hce_ai::AI_Request, hce_ai::AI_Response>>
    request(const std::string& pipelineConfig, const std::vector<std::string>& mediaUri, unsigned suggestedWeight = 0);

    void shutdown();

 private:
    std::shared_ptr<hce_ai::ai_inference::Stub> m_stub;

    inline bool _validateIP(const std::string& addr) const{
        struct sockaddr_in sa;
        // If successful, inet_pton() returns 1 and stores the binary form of the Internet address in the buffer pointed to by dst.
        // If unsuccessful because the input buffer pointed to by src is not a valid string, inet_pton() returns 0.
        // If unsuccessful because the af argument is unknown, inet_pton() returns -1
        return inet_pton(AF_INET, addr.c_str(), &(sa.sin_addr)) > 0;
    };

    std::string m_addr;
    std::string m_port;
  
  const std::string& pipelineConfig = "SomeConfig";
};

GRPCClient::GRPCClient(const std::string& address, const std::string& port) {
    assert((_validateIP(address)));
    m_addr = address;
    m_port = port;
}

GRPCClient::~GRPCClient(){
    shutdown();
}

std::shared_ptr<hce_ai::ai_inference::Stub> GRPCClient::connect() {
    
    std::string target_str = m_addr + ":" + m_port;
    grpc::ChannelArguments ch_args;
    ch_args.SetMaxReceiveMessageSize(-1);
    ch_args.SetMaxSendMessageSize(-1);
    std::shared_ptr<grpc::Channel> channel = grpc::CreateCustomChannel(target_str, grpc::InsecureChannelCredentials(), ch_args);
    m_stub = hce_ai::ai_inference::NewStub(channel);
    assert(m_stub);
    std::cout << "gRPC client connect at:" << target_str << std::endl;

    return m_stub;
}

void GRPCClient::shutdown() {
    std::cout << "gRPC client shutdown." << std::endl;
}

bool GRPCClient::run(const std::string& pipelineConfig, const std::vector<std::string>& mediaUri, unsigned& retCode, std::string& retBody, unsigned suggestedWeight, unsigned streamNum){
    HCE_AI_CLIENT_CHECK_RETURN_IF_FAIL((!pipelineConfig.empty()), false);
    HCE_AI_CLIENT_CHECK_RETURN_IF_FAIL(mediaUri.size(), false);
    
    grpc::ClientContext context;
    std::shared_ptr<grpc::ClientReaderWriter<hce_ai::AI_Request, hce_ai::AI_Response>> stream(
        m_stub->Run(&context));

    hce_ai::AI_Request request;
    request.set_pipelineconfig(pipelineConfig);
    request.set_suggestedweight(suggestedWeight);
    request.set_streamnum(streamNum);
    for(const auto& item: mediaUri) {
        request.add_mediauri(item);
    }
    // auto *dst_ptr = request.mediauri();
    // google::protobuf::RepeatedField<google::protobuf::string> field{mediaUri.begin(), mediaUri.end()};
    // dst_ptr->CopyFrom(field);

    stream->Write(request);

    hce_ai::AI_Response reply;
    std::string reply_msg;
    int reply_status;
    while(stream->Read(&reply)){
        // hce_ai::Stream_Response sr = reply.responses().at("result");
        // std::cout << "got: " <<std::endl;
        // std::cout<< sr.jsonmessages() << std::endl;
        // std::cout << sr.binary() << std::endl;
        reply_msg = reply.message();
        reply_status = reply.status();
        // std::cout << "got: " << msg << std::endl;
    }

    retCode = (unsigned)reply_status;
    retBody = reply_msg;

    stream->WritesDone();

    grpc::Status status = stream->Finish();

    if (status.ok()) {
        return true;
    }
    else {
        std::cout << status.error_code() << ": " << status.error_message() << std::endl;
        return false;
    }
}

std::shared_ptr<grpc::ClientReaderWriter<hce_ai::AI_Request, hce_ai::AI_Response>> GRPCClient::request(
        const std::string& pipelineConfig, const std::vector<std::string>& mediaUri, unsigned suggestedWeight)
{
    // for sanity
    HVA_ASSERT((!pipelineConfig.empty()));
    HVA_ASSERT(mediaUri.size());
    
    grpc::ClientContext context;
    std::shared_ptr<grpc::ClientReaderWriter<hce_ai::AI_Request, hce_ai::AI_Response>> stream(
        m_stub->Run(&context));

    hce_ai::AI_Request request;
    request.set_pipelineconfig(pipelineConfig);
    request.set_suggestedweight(suggestedWeight);
    for(const auto& item: mediaUri) {
        request.add_mediauri(item);
    }
    // auto *dst_ptr = request.mediauri();
    // google::protobuf::RepeatedField<google::protobuf::string> field{mediaUri.begin(), mediaUri.end()};
    // dst_ptr->CopyFrom(field);

    stream->Write(request);

    return stream;
}

}

}

}

#endif //#ifndef HCE_AI_INF_GRPC_CLIENT_HPP
