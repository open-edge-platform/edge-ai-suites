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

#include <boost/exception/all.hpp>

#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>

#include "nodes/CPU-backend/FakeSinkNode.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce{

namespace ai{

namespace inference{

FakeSinkNodeWorker::FakeSinkNodeWorker(hva::hvaNode_t* parentNode):baseResponseNodeWorker(parentNode) {
    
    m_nodeName = ((FakeSinkNode*)getParentPtr())->nodeClassName();
}

/**
 * @brief Called by hva framework for each video frame, Run inference and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void FakeSinkNodeWorker::process(std::size_t batchIdx){
    std::vector<hva::hvaBlob_t::Ptr> vecBlobInput =
        getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});

    if (vecBlobInput.empty()) 
        return;
    
    for (const auto& inBlob : vecBlobInput) {

        hva::hvaVideoFrameWithROIBuf_t::Ptr buf =
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(
                inBlob->get(0));

        HVA_DEBUG("%s %d on frameId %u and streamid %u with tag %d", 
                   m_nodeName.c_str(), batchIdx, inBlob->frameId, inBlob->streamId, buf->getTag());

        // for sanity: check the consistency of streamId, each worker should work on one streamId.
        if (!validateStreamInput(inBlob)) {
            buf->drop = true;
            buf->rois.clear();
        }

        hce::ai::inference::HceDatabaseMeta videoMeta;
        inBlob->get(0)->getMeta(videoMeta);

        int status_code;
        std::string description;
        if(buf->rois.size() != 0){
            status_code = 0u;
            description = "succeeded";
        }
        else{
            status_code = 1u;
            description = "noRoiDetected";
        }
        m_jsonTree.clear();
        m_jsonTree.put("status_code", status_code);
        m_jsonTree.put("description", description);

        std::stringstream ss;
        boost::property_tree::json_parser::write_json(ss, m_jsonTree);

        baseResponseNode::Response res;
        res.status = 0;
        res.message = ss.str();

        HVA_DEBUG("Emit: %s on frame id %d", res.message.c_str(), buf->frameId);

        dynamic_cast<FakeSinkNode*>(getParentPtr())
            ->emitOutput(res, (baseResponseNode*)getParentPtr(), nullptr);

        if(buf->getTag() == hvaBlobBufferTag::END_OF_REQUEST){
            dynamic_cast<FakeSinkNode*>(getParentPtr())->addEmitFinishFlag();
            HVA_DEBUG("Receive finish flag on framid %u and streamid %u", inBlob->frameId, inBlob->streamId);
        }
    }

    // check whether to trigger emitFinish()
    if (dynamic_cast<FakeSinkNode*>(getParentPtr())->isEmitFinish()) {
        // coming batch processed done
        HVA_DEBUG("Emit finish!");
        dynamic_cast<FakeSinkNode*>(getParentPtr())->emitFinish((baseResponseNode*)getParentPtr(), nullptr);
    }
}

FakeSinkNode::FakeSinkNode(std::size_t totalThreadNum):baseResponseNode(1, 0,totalThreadNum){
    this->transitStateTo(hva::hvaState_t::configured);
}

std::shared_ptr<hva::hvaNodeWorker_t> FakeSinkNode::createNodeWorker() const{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new FakeSinkNodeWorker((hva::hvaNode_t*)this));
} 

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(FakeSinkNode, FakeSinkNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}

}

}