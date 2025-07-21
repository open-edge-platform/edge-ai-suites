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

#include "utils/testUtils.hpp"
#include <sys/timeb.h>
#include <opencv2/opencv.hpp>
#include <opencv2/imgcodecs.hpp>

#include "nodes/databaseMeta.hpp"
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>

using namespace hce::ai::inference;

cv::Mat composeFrameInputWithROI(const std::string& path, unsigned x=0, unsigned y=0, unsigned w=0, unsigned h=0) {
    cv::Mat image = cv::imread(path, cv::ImreadModes::IMREAD_COLOR);
    if (w > 0 && h > 0) {
        // to-do
    }
    return image;
}

class dummyworker : public hva::hvaNodeWorker_t{
public:
    dummyworker(hva::hvaNode_t* parentNode):hva::hvaNodeWorker_t(parentNode){
        
    };

    void process(std::size_t batchIdx) override{
        std::cout<<"\nThis is a dummy output node worker."<<std::endl;

        getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});
    };
private:

};

class dummy : public hva::hvaNode_t{
public:
    dummy():hva::hvaNode_t(1, 0, 1){
        transitStateTo(hva::hvaState_t::configured);
    };

    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override{
        return std::shared_ptr<hva::hvaNodeWorker_t>(new dummyworker((hva::hvaNode_t*)this));
    };

    virtual const std::string nodeClassName() const override{ return "dummy";};

private:

};

int main(int argc, char** argv){

    try
    {
        // Check command line arguments.
       if(argc != 4)
        {
            std::cerr <<
                "Usage: testAiNode <repeats> <configure_file> <image_folder>\n" <<
                "Example:\n" <<
                "    testAiNode 1 ../../ai_inference/test/configs/unit_tests/UTcpuDetection-vehicle-evi001 /path/to/image_folder \n" <<
                "-------------------------------------------------------------------------------- \n" <<
                "Environment requirement:\n" <<
                "   export HVA_NODE_DIR=/opt/hce-core/middleware/ai/build/lib \n" <<
                "   source /opt/intel/openvino*/setupvars.sh \n";
            return EXIT_FAILURE;
        }
        unsigned repeats(atoi(argv[1]));
        std::string config_file(argv[2]);
        std::string imageFolder(argv[3]);

        hvaLogger.setLogLevel(hva::hvaLogger_t::LogLevel::DEBUG);
        hvaLogger.enableProfiling();

        hva::hvaNodeRegistry::getInstance().init(HVA_NODE_REGISTRY_NO_DLCLOSE | HVA_NODE_REGISTRY_RTLD_GLOBAL);

        std::string contents;

        std::ifstream in(config_file, std::ios::in);
        if (in){
            in.seekg(0, std::ios::end);
            contents.resize(in.tellg());
            in.seekg(0, std::ios::beg);
            in.read(&contents[0], contents.size());
            in.close();
        }

        /**
         * processing input
         **/
        std::vector<std::string> mediaVector;
        HVA_DEBUG("testAiNode load images from folder: %s", imageFolder.c_str());
        getAllFiles(imageFolder, mediaVector);
        std::sort(mediaVector.begin(), mediaVector.end());
        
        std::vector<cv::Mat> inputs;
        for(const auto& item: mediaVector){
            HVA_DEBUG("reading image path: %s", item.c_str());
            cv::Mat decodedMat = composeFrameInputWithROI(item);
            inputs.push_back(decodedMat);
        }
        HVA_INFO("inputs size is: %d", inputs.size());

        hva::hvaPipelineParser_t parser;
        std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());

        parser.parseFromString(contents, *pl);

        pl->prepare();

        HVA_INFO("Pipeline Start: ");
        pl->start();

        for (size_t cnt = 0; cnt < repeats; cnt ++) {
            unsigned frameIdx = 0;
            for (size_t b_ix = 0; b_ix < inputs.size(); b_ix ++) {

                cv::Mat decodedImage = inputs[b_ix];
                unsigned width = decodedImage.size().width;
                unsigned height = decodedImage.size().height;
                unsigned channel = decodedImage.channels();

                HVA_DEBUG("Input image at width: %d, height: %d and channel: %d", width, height, channel);
                std::string toSend((char*)decodedImage.data, width*height*channel);
                hva::hvaVideoFrameWithROIBuf_t::Ptr hvabuf = hva::hvaVideoFrameWithROIBuf_t::make_buffer<uint8_t*>((uint8_t *)toSend.c_str(), toSend.size());
                
                hva::hvaROI_t roi;
                roi.x = 0;
                roi.y = 0;
                roi.width = width;
                roi.height = height;

                hvabuf->rois.push_back(std::move(roi));

                hvabuf->frameId = frameIdx;
                hvabuf->width = width;
                hvabuf->height = height;
                hvabuf->stride[0] = channel * width;
                hvabuf->drop = false;

                HceDatabaseMeta meta;
                meta.localFilePath = mediaVector[b_ix];
                meta.bufType = HceDataMetaBufType::BUFTYPE_UINT8;
                hvabuf->setMeta(meta);
                if (b_ix == inputs.size()-1) {
                    // last one in the batch. Mark it
                    HVA_DEBUG("Set tag 1 on frame %d", frameIdx);
                    hvabuf->tagAs(1);
                }
                else{
                    hvabuf->tagAs(0);
                }
                auto jpegBlob = hva::hvaBlob_t::make_blob();
                jpegBlob->frameId = frameIdx;
                jpegBlob->push(hvabuf);

                frameIdx ++;
                
                pl->sendToPort(jpegBlob, "Input", 0, std::chrono::milliseconds(0));

            }
        }

        // wait till pipeline consuming all input frames
        // this is the maximum processing time as estimated, not stand for the real duration.
        int estimate_latency = repeats * std::max(30, int(0.1 * inputs.size()));  // 100ms for each image
        HVA_INFO("going to sleep for %d s", estimate_latency);
        std::this_thread::sleep_for(std::chrono::seconds(estimate_latency));
        
        HVA_INFO("going to stop");
        pl->stop();
        HVA_INFO("hva pipeline stopped.");

        return 0;
    }
    catch(std::exception const& e)
    {
        std::cerr << "Error: " << e.what() << std::endl;
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
/**
 * example for expected logs:
 *   [DEBUG] [144] [1639036815434]: LLOutputNode.cpp:125 process Emit: {
    "status_code": "0",
    "description": "succeeded",
    "roi_info": [
        {
            "roi": [
                "1103",
                "451",
                "84",
                "25"
            ],
            "feature_vector": "",
            "roi_class": "license_plate",
            "roi_score": "0.93460416793823242",
            "track_id": "0",
            "track_status": "0",
            "attribute": {
                "color": "",
                "color_score": "0",
                "type": "",
                "type_score": "0"
            },
            "license_plate": ""
        }
    ]
}
 on frame id 1

*/
