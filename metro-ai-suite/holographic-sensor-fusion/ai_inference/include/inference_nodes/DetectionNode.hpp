/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2024 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef __HCE_AI_INF_DETECTION_NODE_HPP__
#define __HCE_AI_INF_DETECTION_NODE_HPP__

#include <map>
#include <string>
#include <dlfcn.h>

#include "modules/inference_util/detection/det_post_impl.hpp"
#include "inference_nodes/base/baseImageInferenceNode.hpp"

namespace hce{

namespace ai{

namespace inference{


class DetectionNode : public baseImageInferenceNode{
public:

    DetectionNode(std::size_t totalThreadNum);

    virtual ~DetectionNode() override;

    /**
    * @brief Parse params, called by hva framework right after node instantiate.
    * @param config Configure string required by this node.
    */
    hva::hvaStatus_t configureByString(const std::string& config);
    
    /**
    * @brief prepare and intialize this hvaNode_t instance. Create ImageInferenceInstance
    * 
    * @param void
    * @return hvaSuccess if success
    */
    hva::hvaStatus_t prepare() override;

    /**
    * @brief Constructs and returns a node worker instance: DetectionNodeWorker.
    * @param void
    */
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const;

    /**
    * @brief return the human-readable name of this node class
    * 
    * @param void
    * @return node class name
    */
    virtual const std::string nodeClassName() {
        return "DetectionNode";
    };

    /**
    * @brief get the post-processor of this node class
    * 
    * @param void
    * @return post processor instance
    */
    virtual const DetectionPostProcessor::Ptr getPostProcessors() {
        return m_postProcessor;
    };

    /**
    * @brief get the custom dynamic library for post-processor of this node class
    * 
    * @param void
    * @return dynamic library instance
    */
    virtual void* getPostProcessorCustomHandle() {
        return m_postProcessorCustomHandle;
    };

private:

    float m_threshold;
    int m_maxROI;
    std::vector<std::string> m_filterLabels;

    void* m_postProcessorCustomHandle;
    DetectionPostProcessor::Ptr m_postProcessor;
};


class DetectionNodeWorker : public baseImageInferenceNodeWorker{
public:
    DetectionNodeWorker(hva::hvaNode_t* parentNode,
                            InferenceProperty inferenceProperty,
                            ImageInferenceInstance::Ptr instance);

    virtual ~DetectionNodeWorker() override;

    /**
     * @brief would be called at the end of each process() to send outputs to the
     * downstream nodes.
     * @return void
     */
    virtual void processOutput(
        std::map<std::string, InferenceBackend::OutputBlob::Ptr> blobs,
        std::vector<std::shared_ptr<InferenceBackend::ImageInference::IFrameBase>> frames);
    
    // custom post processor function
    typedef std::string (*load_customPostProcessor)(
        std::map<std::string, float*> blob_data,
        std::map<std::string, size_t> blob_length, float class_conf_thresh, size_t targetBatchId);

private:

    void* m_postProcessorCustomHandle;
    DetectionPostProcessor::Ptr m_postProcessor;
    
    /**
     * @brief erase detected rois outside filter region
     * @param filter filter region
     * @param rois detected rois
     */
    void filterROI(const hva::hvaROI_t& filter, std::vector<hva::hvaROI_t>& rois, float filter_thresh = 0.5f);
    
    /**
     * @brief run post processing on model outputs
     * @param blobData <layer_name, inference_blob_data>
     * @param blobLength <layer_name, blob_length>
     * @param hvaROIs save the parsed roi results
     * @param heightInput original image height
     * @param widthInput original image width
     * @return boolean
     */
    bool runPostproc(
        std::map<std::string, float*> blobData,
        std::map<std::string, size_t> blobLength,
        std::vector<hva::hvaROI_t>& hvaROIs, size_t heightInput, size_t widthInput, size_t targetBatchId = 0);
};

} // namespace inference

} // namespace ai

} // namespace hce

#endif //#ifndef __HCE_AI_INF_DETECTION_NODE_HPP__