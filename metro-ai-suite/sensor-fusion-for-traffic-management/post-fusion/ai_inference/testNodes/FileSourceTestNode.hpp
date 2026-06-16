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

#include <thread>
#include <iostream>
#include <atomic>

#include <inc/api/hvaPipeline.hpp>
// #include <inc/api/hvaBlob.hpp>

using ms = std::chrono::milliseconds;

struct FrameData{
    int frameId;
    std::vector<float> frameFeature;//include 512 data with floats type.
};

class FileSourceTestNodeWorker : public hva::hvaNodeWorker_t{
public:
    FileSourceTestNodeWorker(hva::hvaNode_t* parentNode, std::string name);

    void process(std::size_t batchIdx) override;
private:
    std::string m_name;
};

class FileSourceTestNode : public hva::hvaNode_t{
public:
    FileSourceTestNode(std::size_t inPortNum, std::size_t outPortNum, std::size_t totalThreadNum, std::string name);

    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override;

    std::string name();

    unsigned fetch_increment();

    virtual const std::string nodeClassName() const override{ return "FileSourceTestNode";};

    virtual hva::hvaStatus_t configureByString(const std::string& config);

    virtual hva::hvaStatus_t rearm();

private:
    std::string m_name;
    std::atomic<unsigned> ctr;
};

HVA_ENABLE_DYNAMIC_LOADING(FileSourceTestNode, FileSourceTestNode(0, 1, threadNum, "defaultName"))