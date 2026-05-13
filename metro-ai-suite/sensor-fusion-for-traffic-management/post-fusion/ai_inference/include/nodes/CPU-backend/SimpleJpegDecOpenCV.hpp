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

#ifndef SIMPLE_JPEG_DEC_OPENCV_HPP
#define SIMPLE_JPEG_DEC_OPENCV_HPP

#include <iostream>
#include <memory>
#include <thread>
#include <inc/api/hvaPipeline.hpp>
#include <inc/util/hvaUtil.hpp>
namespace hce{

namespace ai{

namespace inference{

class SimpleJpegDecOpenCV : public hva::hvaNode_t{
public:
    SimpleJpegDecOpenCV(std::size_t totalThreadNum);

    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override;

private:
};

class SimpleJpegDecOpenCVWorker : public hva::hvaNodeWorker_t{
public:
    SimpleJpegDecOpenCVWorker(hva::hvaNode_t* parentNode);
    ~SimpleJpegDecOpenCVWorker();

    void process(std::size_t batchIdx) override;
    void processByFirstRun(std::size_t batchIdx) override;
    void processByLastRun(std::size_t batchIdx) override;

    hva::hvaStatus_t rearm() override;
    hva::hvaStatus_t reset() override;

    void init() override;
    void deinit() override;

private:

};

}

}

}
#endif /*SIMPLE_JPEG_DEC_OPENCV_HPP*/
