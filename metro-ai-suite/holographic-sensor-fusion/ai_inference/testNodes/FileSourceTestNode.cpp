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

#include <FileSourceTestNode.hpp>

FileSourceTestNodeWorker::FileSourceTestNodeWorker(hva::hvaNode_t* parentNode, std::string name):
    hva::hvaNodeWorker_t(parentNode), m_name(name){

}

void FileSourceTestNodeWorker::process(std::size_t batchIdx){
    std::cout<<"\nThis is a FileSourceTestNodeWorker node worker."<<std::endl;
    unsigned temp = dynamic_cast<FileSourceTestNode*>(hvaNodeWorker_t::getParentPtr())->fetch_increment();
    FrameData result;
    result.frameFeature = std::vector<float>(512);
    result.frameId = temp;
    auto buf = hva::hvaBuf_t::make_buffer(std::move(result), sizeof(result));
    std::cout<<"Buf inited"<<std::endl;

    auto blob = hva::hvaBlob_t::make_blob();
    blob->push(buf);
    std::cout<<"Value pushed"<<std::endl;
    std::this_thread::sleep_for(ms(10));
    sendOutput(blob,0);

    if(temp == 10){
        getParentPtr()->emitEvent(hvaEvent_EOS, nullptr);
    }
}

FileSourceTestNode::FileSourceTestNode(std::size_t inPortNum, std::size_t outPortNum, std::size_t totalThreadNum, std::string name)
        :hva::hvaNode_t(inPortNum, outPortNum, totalThreadNum), m_name(name){
    ctr = 1;
    transitStateTo(hva::hvaState_t::configured);
}

std::shared_ptr<hva::hvaNodeWorker_t> FileSourceTestNode::createNodeWorker() const{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new FileSourceTestNodeWorker((hva::hvaNode_t*)this,"MyNodeWorkerInst"));
}

hva::hvaStatus_t FileSourceTestNode::configureByString(const std::string& config){
    savetoConfigString(config);
    std::cout<<"Config String " << config << " saved!"<<std::endl;
    return hva::hvaSuccess;
}

std::string FileSourceTestNode::name(){
    return m_name;
}

unsigned FileSourceTestNode::fetch_increment(){
    return ctr++;
}

hva::hvaStatus_t FileSourceTestNode::rearm(){
    ctr = 1;
    return hva::hvaSuccess;
}
