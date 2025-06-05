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

#ifndef HVA_HVAMETAROI_HPP
#define HVA_HVAMETAROI_HPP

#include <chrono>
#include <memory>
#include <type_traits>
#include <functional>
#include <iostream>
#include <inc/util/hvaUtil.hpp>
#include <inc/meta/hvaMeta.hpp>

namespace hva{

class HVA_DECLSPEC hvaMetaROI_t{
public:
    using Ptr = std::shared_ptr<hvaMetaROI_t>;

    hvaMetaROI_t(): x(0), y(0), width(0), height(0), labelIdDetection(0), confidenceDetection(0.0) {
        
    };

    ~hvaMetaROI_t(){
        
    };

    /**************************
     * Meta data related APIs *
     **************************/

    template <typename META_T>
    hvaStatus_t setMeta(META_T metadata);

    template <typename META_T>
    hvaStatus_t eraseMeta();

    template <typename META_T>
    hvaStatus_t getMeta(META_T& metadata) const;

    hvaStatus_t eraseAllMeta();

    template <typename META_T>
    bool containMeta() const;

    /**************************************
     * public fields of hvaMetaROI_t*
     **************************************/
    int x;                                      // Left of ROI
    int y;                                      // Top of ROI
    int width;                                  // Width of ROI
    int height;                                 // Height of ROI
    
    std::string labelDetection;                 // Detection label
    int labelIdDetection;                       // Detection label id
    double confidenceDetection;                 // Detection confidence
    
private:
    hvaMetaMap_t m_meta;
};

template <typename META_T>
hvaStatus_t hvaMetaROI_t::setMeta(META_T metadata){
    if(m_meta.add(std::move(metadata)))
        return hvaSuccess;
    else
        return hvaFailure;
};

template <typename META_T>
hvaStatus_t hvaMetaROI_t::eraseMeta(){
    if(m_meta.erase<META_T>())
        return hvaSuccess;
    else
        return hvaFailure;
};

template <typename META_T>
hvaStatus_t hvaMetaROI_t::getMeta(META_T& metadata) const{
    if(m_meta.get(metadata))
        return hvaSuccess;
    else
        return hvaFailure;
};

template <typename META_T>
bool hvaMetaROI_t::containMeta() const{
    return m_meta.contain<META_T>();
};

}
#endif // HVA_HVAMETAROI_HPP