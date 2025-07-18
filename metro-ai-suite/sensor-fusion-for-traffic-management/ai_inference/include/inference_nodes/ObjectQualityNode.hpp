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

#ifndef __HCE_AI_INF_OBJECT_QUALITY_NODE_HPP__
#define __HCE_AI_INF_OBJECT_QUALITY_NODE_HPP__

#include <map>
#include <string>

#include "modules/quality.hpp"
#include "inference_nodes/base/baseImageInferenceNode.hpp"

#ifdef ENABLE_VAAPI
    #include "modules/vaapi/utils.hpp"
#endif

namespace hce{

namespace ai{

namespace inference{

class ObjectQualityNode : public baseImageInferenceNode{
public:

    ObjectQualityNode(std::size_t totalThreadNum);

    virtual ~ObjectQualityNode() override;

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
    * @brief Constructs and returns a node worker instance: ObjectQualityNodeWorker.
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
        return "ObjectQualityNode";
    };

    // /**
    // * @brief get the post-processor of this node class
    // * 
    // * @param void
    // * @return post processor instances
    // */
    // virtual const std::map<std::string, ClassificationPostProcessor::Ptr> getPostProcessors() {
    //     return m_postProcessors;
    // };

    /**
    * @brief get the quality predictor (opencv) of this node class
    * 
    * @param void
    * @return post processor instances
    */
    virtual const QualityPredictor::Ptr getQualityPredictor() {
        return m_qualityPredictor;
    };

private:
    QualityPredictor::Ptr m_qualityPredictor;
//     std::map<std::string, ClassificationPostProcessor::Ptr> m_postProcessors;                   // pair: <layer_name, converter>
};


class ObjectQualityNodeWorker : public baseImageInferenceNodeWorker{
public:
    ObjectQualityNodeWorker(hva::hvaNode_t* parentNode,
                            InferenceProperty inferenceProperty,
                            ImageInferenceInstance::Ptr instance);

    virtual ~ObjectQualityNodeWorker() override;
    
    /**
     * @brief Called by hva framework for each video frame, Run inference and pass
     * output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx);
    
    /**
     * @brief would be called at the end of each process() to send outputs to the
     * downstream nodes.
     * @return void
     */
    virtual void processOutput(
        std::map<std::string, InferenceBackend::OutputBlob::Ptr> blobs,
        std::vector<std::shared_ptr<InferenceBackend::ImageInference::IFrameBase>> frames);

private:
    QualityPredictor::Ptr m_qualityPredictor;
//     std::map<std::string, ClassificationPostProcessor::Ptr> m_postProcessors;   // pair: <layer_name, post_processor>
};

} // namespace inference

} // namespace ai

} // namespace hce

#endif //#ifndef __HCE_AI_INF_OBJECT_QUALITY_NODE_HPP__