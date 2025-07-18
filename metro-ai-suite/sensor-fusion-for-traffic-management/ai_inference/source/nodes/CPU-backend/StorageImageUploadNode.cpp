/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2022 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#include <stdlib.h>
#include <time.h>
#include <iostream>
#include <sys/types.h>
#include <dirent.h>
#include <vector>
#include <string.h>
#include <thread>
#include <inttypes.h>

#include <inc/util/hvaConfigStringParser.hpp>

#include <boost/exception/all.hpp>

#include "common/base64.hpp"
#include "nodes/CPU-backend/StorageImageUploadNode.hpp"

namespace hce{
namespace ai{

namespace inference{

StorageImageUploadNode::StorageImageUploadNode(std::size_t totalThreadNum):hva::hvaNode_t(1, 1, totalThreadNum){

}

StorageImageUploadNode::~StorageImageUploadNode(){

}

/**
* @brief Parse params, called by hva framework right after node instantiate.
* @param config Configure string required by this node.
*/
hva::hvaStatus_t StorageImageUploadNode::configureByString(const std::string& config){
    if (config.empty()) return hva::hvaFailure;

    if (!m_configParser.parse(config)) {
        HVA_ERROR("Illegal parse string!");
        return hva::hvaFailure;
    }

    // video or image
    std::string mediaType;
    m_configParser.getVal<std::string>("MediaType", mediaType);
    if (mediaType.empty()) {
        HVA_ERROR("Must define the media type in config!");
        return hva::hvaFailure;
    }

    std::string dataSource = "vehicle";
    m_configParser.getVal<std::string>("DataSource", dataSource);

    // requireROI:
    // > if true: only upload images with rois
    // > else: upload all coming images
    bool requireROI = true;
    m_configParser.getVal<bool>("RequireROI", requireROI);

    m_mediaType = mediaType;
    m_dataSource = dataSource;
    m_requireROI = requireROI;
    
    transitStateTo(hva::hvaState_t::configured);
    return hva::hvaSuccess;
}
 
/**
* @brief Constructs and returns a node worker instance: StorageImageUploadNodeWorker.
* @param void
*/
std::shared_ptr<hva::hvaNodeWorker_t> StorageImageUploadNode::createNodeWorker()
    const {
  return std::shared_ptr<hva::hvaNodeWorker_t>(new StorageImageUploadNodeWorker(
      (hva::hvaNode_t*)this, m_mediaType, m_dataSource, m_requireROI));
}

StorageImageUploadNodeWorker::StorageImageUploadNodeWorker(
    hva::hvaNode_t* parentNode, const std::string& mediaType,
    const std::string& dataSource, bool requireROI)
    : hva::hvaNodeWorker_t(parentNode),
      m_ctr(0u),
      m_mediaType(mediaType),
      m_dataSource(dataSource),
      m_requireROI(requireROI) {}

void StorageImageUploadNodeWorker::init(){

    m_configmapFile = "/opt/hce-configs/media_storage_configmap.json";
    m_storageClient = std::unique_ptr<hce::storage::Media_Storage>(new hce::storage::Media_Storage());
    m_storageClient->global_init();
    m_storageClient->init(m_configmapFile);
    HVA_DEBUG("Media storage client init using config file at %s", m_configmapFile.c_str());
    
}

/**
 * @brief generate media attrib
 * for example:
 * post_media_attributes = {"media_id": "0044","media_uri": 17301039306058ec87974571990a379e7696d0fb, 
 *                          "object_name": "media", "media_type_id": "01", "timestamp": "12345678"};      
*/
bool StorageImageUploadNodeWorker::generateMediaAttrib(const hva::hvaVideoFrameWithROIBuf_t::Ptr& ptrBuf, const std::string& URI,
                                                       const HceDatabaseMeta& originMeta, std::string& mediaAttrib, 
                                                       const std::string& originURI) {
    // to-do: origin_uri should be inserted to the media table
    // so that the saved snapshot can be associated with original video
    // `ancestor`??

    std::string media_type_id;
    std::string media_type;

    if (m_mediaType == "image" || m_mediaType == "video") {
        // we save snapshots for video, so media_type_id should be same as "image"
        media_type_id = "01";
    } else {
        HVA_ERROR("Unknown media type: %s", m_mediaType.c_str());
        return false;
    }
    
    // generate media attributes with pre-defined schema
    mediaAttrib = "{\"media_id\":\"" + std::to_string(ptrBuf->frameId) +
                    "\", \"media_uri\":\"" + URI +
                    "\", \"object_name\": \"media\"," +
                    "\"media_type_id\":\"" + media_type_id +
                    "\",\"capture_source_id\":\"" + originMeta.captureSourceId +
                    "\",\"size\":\"" + std::to_string(ptrBuf->width * ptrBuf->height * 3) +
                    "\",\"resolution\":\"" + std::to_string(ptrBuf->width) + "x" + std::to_string(ptrBuf->height) +
                    "\",\"frame_index\":\"" + std::to_string(ptrBuf->frameId) +
                    "\",\"format\":\"jpg" +
                    "\",\"timestamp\":\"" + std::to_string(originMeta.timeStamp) +
                    "\",\"ancestor\":\"" + originURI +
                    "\"}";
    return true;
}

/**
 * @brief Called by hva framework for each video frame, Run inference and pass
 * output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void StorageImageUploadNodeWorker::process(std::size_t batchIdx){

    // get input blob from port 0
    std::vector<hva::hvaBlob_t::Ptr> vecBlobInput =
        getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});

    // input blob is not empty
    for (const auto& blob : vecBlobInput) {
        
        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrVideoBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(blob->get(0));

        HVA_DEBUG(
            "Storage image upload node %d on frameId %u and streamid %u with tag %d",
            batchIdx, blob->frameId, blob->streamId, ptrVideoBuf->getTag());

        // coming empty blob
        if(ptrVideoBuf->drop){

            ptrVideoBuf->rois.clear();

            HVA_DEBUG("Storage image upload node dropped a frame on frameid %u and streamid %u", blob->frameId, blob->streamId);
            sendOutput(blob, 0, std::chrono::milliseconds(0));
            return;
        }

        // start processing
        auto procStart = std::chrono::steady_clock::now();

        // read image data from buffer
        const uint8_t* pBuffer = ptrVideoBuf->get<uint8_t*>();
        if(pBuffer == NULL){
            HVA_DEBUG("Storage image upload node receiving an empty buffer on frameid %u and streamid %u, skipping", blob->frameId, blob->streamId);
            ptrVideoBuf->rois.clear();
            sendOutput(blob, 0, std::chrono::milliseconds(0));
            return;
        }

        if (m_requireROI) {
            // only upload images with valid rois
            HceDatabaseMeta meta;
            blob->get(0)->getMeta(meta);
            std::vector<hva::hvaROI_t> collectedROIs;
            // processing all coming rois
            for(size_t roiId = 0; roiId < ptrVideoBuf->rois.size(); ++roiId){
                if (meta.ignoreFlags.count(roiId) > 0 && meta.ignoreFlags[roiId] == true) {
                    // should be ignored in this node
                    // do nothing
                }
                else {
                    collectedROIs.push_back(ptrVideoBuf->rois[roiId]);
                }
            }
            if (collectedROIs.size() == 0) {
                HVA_DEBUG("Storage image upload node receiving none rois on frameid %u and streamid %u, skipping", blob->frameId, blob->streamId);
                sendOutput(blob, 0, std::chrono::milliseconds(0));
                return;
            }
        }

        int input_height = ptrVideoBuf->height;
        int input_width = ptrVideoBuf->width;

        try
        {
            /**
             * @brief 
             * 1. encode image
             * 2. generate media_uri
             * 3. upload bgr buffer to minIO database
             * 4. replace media_uri in blob as currently generated uri
             */

            // start to encode image to jpg from buffer
            std::vector<unsigned char> img_encode;
            HVA_DEBUG("Storage image upload node encode image from buffer");
            cv::Mat decodedImage(input_height, input_width, CV_8UC3, (uint8_t*)pBuffer);
            cv::imencode(".jpg", decodedImage, img_encode);
            std::string bgrMediaContent(img_encode.begin(), img_encode.end());
            HVA_DEBUG("Storage image upload node encode image from buffer done");

            std::string image_uri;
            m_storageClient->generate_media_URI(m_mediaType, m_dataSource, image_uri);
            HVA_DEBUG("Success to generate media URI: %s", image_uri.c_str());

            HceDatabaseMeta meta;
            if(blob->get(0)->getMeta(meta) == hva::hvaSuccess){
                HVA_DEBUG("Storage image upload node received meta, mediauri: %s", meta.mediaUri.c_str());
            }

            // generate media attrib for current image
            std::string post_media_attributes;
            if (!generateMediaAttrib(ptrVideoBuf, image_uri, meta, post_media_attributes, meta.mediaUri))  {
                HVA_ERROR("Failed to generate media attrib with media_uri: %s at frameid: %u", image_uri.c_str(), ptrVideoBuf->frameId);
            }
            else {
                HVA_DEBUG("post_media_attributes at frameid: %u, got:\n%s", ptrVideoBuf->frameId, post_media_attributes.c_str());

                // upload media to minIO
                // upload meta-data to greenplum
                if (m_storageClient->upload_media_buffer(
                        m_configmapFile, image_uri, bgrMediaContent, bgrMediaContent.size(),
                        post_media_attributes) ==
                    hce::storage::status_code::normal) {
                  HVA_DEBUG(
                      "Success to upload_media_buffer with media_uri: %s at "
                      "frameid: %u",
                      image_uri.c_str(), ptrVideoBuf->frameId);
                } else {
                  HVA_ERROR(
                      "Failed to upload_media_buffer with media_uri: %s at "
                      "frameid: %u",
                      image_uri.c_str(), ptrVideoBuf->frameId);
                }
                
                // replace original media uri with newly generated uri
                // specifically: video_media_uri => snapshot_image_media_uri
                meta.mediaUri = image_uri;
                ptrVideoBuf->setMeta(meta);
            }
                    
            // process done
            auto procEnd = std::chrono::steady_clock::now();
            auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(procEnd - procStart).count();

            // calculate duration
            m_durationAve = (m_durationAve * (int)m_cntProcessEnd + duration) / ((int)m_cntProcessEnd + 1);
            m_cntProcessEnd ++;
            HVA_DEBUG("Storage image upload node average duration is %ld ms, at processing cnt: %d", 
                        (int)m_durationAve, (int)m_cntProcessEnd);
            
            HVA_DEBUG("Submiting storage image upload node on image with w: %d, h: %d, with rois: %d", input_width, input_height, ptrVideoBuf->rois.size());
        }
        catch(std::exception& e)
        {
            std::cout << e.what() << std::endl;
            HVA_ERROR("Storage image upload node exception error with frameid %u and streamid %u", blob->frameId, blob->streamId);

        }
        catch(...)
        {
            HVA_ERROR("Storage image upload node exception error with frameid %u and streamid %u", blob->frameId, blob->streamId);
        }

        HceDatabaseMeta meta;
        if(blob->get(0)->getMeta(meta) == hva::hvaSuccess){
            HVA_DEBUG("Storage image upload node sends meta to next buffer, mediauri: %s", meta.mediaUri.c_str());
        }

        // always send blob data out, even uploading failed.
        HVA_DEBUG("Storage image upload node sending blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
        sendOutput(blob, 0, std::chrono::milliseconds(0));
        HVA_DEBUG("Storage image upload node completed sent blob with frameid %u and streamid %u", blob->frameId, blob->streamId);

        HVA_DEBUG("Storage image upload node loop end, frame id is %d, stream id is %d\n", blob->frameId, blob->streamId);

    }
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(StorageImageUploadNode, StorageImageUploadNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}
}
}
