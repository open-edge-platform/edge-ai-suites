/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2022-2023 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#include "testUtils.hpp"
#include "nodes/base/baseResponseNode.hpp"
#include "nodes/databaseMeta.hpp"
#include <inc/impl/hvaState.hpp>

#include <opencv2/opencv.hpp>
#include <opencv2/imgcodecs.hpp>
#include <gtest/gtest.h>
#include <sys/timeb.h>
#include <boost/pool/object_pool.hpp>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>

using namespace hce::ai::inference;
bool g_finishTask;
std::mutex g_mutex;

/**
 * @brief register listener for gtest
 * key functions:
 *  > onEmit: write response body for each processed frame.
 *  > onFinish: reply to client after request frames all finished processing.
*/
class _gtestReplyListener: public baseResponseNode::EmitListener{
public:
    _gtestReplyListener(std::shared_ptr<hva::hvaPipeline_t> pl)
            :baseResponseNode::EmitListener(), m_pl(pl) {

                // record the starting time
                m_start = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
                {
                    std::lock_guard<std::mutex> lg(g_mutex);
                    g_finishTask = false;
                }

                // for sanity check
                if (!m_pl) {
                    HCE_AI_ASSERT(false);
                    HVA_ERROR("invalid pipeline!");
                }
            };
    
    /**
     * @brief write response body for each processed frame.
     * @param res response body
     * @param node outputNode who sends response here
    */
    virtual void onEmit(baseResponseNode::Response res, const baseResponseNode* node, void* data) override{

        // for sanity check
        if (!m_pl) {
            HCE_AI_ASSERT(false);
            HVA_ERROR("invalid pipeline!");
        }

        if(m_pl->getState() == hva::hvaState_t::running){
            
            // record results for each frame into m_frames
            m_frame.clear();
            std::stringstream ss(res.message); 
            boost::property_tree::read_json(ss, m_frame);
            m_frames.push_back(std::make_pair("", m_frame));
        }
        else{
            // if not in running state, it may be abnormally interrupted
            HCE_AI_ASSERT(false);
            HVA_ERROR("Pipeline no longer exists at reply listener destruction");
        }
    };

    /**
     * @brief  reply to client after request frames all finished processing.
     * @param node outputNode who sends response here
    */
    virtual void onFinish(const baseResponseNode* node, void* data) override{

        // for sanity check
        if (!m_pl) {
            HCE_AI_ASSERT(false);
            HVA_ERROR("invalid pipeline!");
        }
        
        if(m_pl->getState() == hva::hvaState_t::running) {
            
            // latency for this inference process
            uint64_t end = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
            uint64_t latency = end - m_start;

            // construct final results as json-style str
            m_jsonTree.add_child("result", m_frames);
            m_jsonTree.put("latency(ms)", latency);
            m_jsonTree.put("frames", m_frames.size());
            std::stringstream ss;
            boost::property_tree::json_parser::write_json(ss, m_jsonTree);
            printf("process finished:\n %s", ss.str().c_str());

            // refresh the starting time
            m_start = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();

            {
                std::lock_guard<std::mutex> lg(g_mutex);
                g_finishTask = true;
            }
        }
        else{
            // if not in running state, it may be abnormally interrupted
            HCE_AI_ASSERT(false);
            HVA_ERROR("Pipeline no longer exists at reply listener destruction");
        }
        
    };

private:
    std::shared_ptr<hva::hvaPipeline_t> m_pl;
    boost::property_tree::ptree m_jsonTree;
    boost::property_tree::ptree m_frame;
    boost::property_tree::ptree m_frames;
    uint64_t m_start;
};

/**
 * @brief load image data from ./demo.
 * @param inputs fed with loaded data
 * 
 * @return boolean on success status
*/
bool loadLocalData(std::vector<std::string>& inputs) {

    // specific directory: ${HCE-REPO}/middleware/ai/ai_inference/test/demo
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    const std::string data_path = folder.string() + "/demo/images";

    // load all image files from data_path, fill in the vector: inputs
    if (!getAllFiles(data_path, inputs)) {
        return false;
    }

    // if none images are loaded, it's invalid
    if (inputs.size() == 0) {
        return false;
    }

    // sort by filename
    std::sort(inputs.begin(), inputs.end());

    return true;
}

/**
 * @brief load image data from ./demo.
 * @param inputs fed with loaded data
 * 
 * @return boolean on success status
*/
bool loadLocalVideoData(std::vector<std::string>& inputs) {

    // specific video path: ${HCE-REPO}/middleware/ai/ai_inference/test/demo/road_barrier_1920_1080.h264
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    const std::string data_path = folder.string() + "/demo/road_barrier_1920_1080.h264";

    // check directory existence
    if (!checkPathExist(data_path)) {
        return false;
    }
    inputs.push_back(data_path);

    return true;
}

/**
 * @brief build ai pipeline
 * @param pl fed with prepared pipeline
 * 
 * @return boolean on success status
*/
bool preparePipeline(std::shared_ptr<hva::hvaPipeline_t>& pl, const std::string &config_file) {
    
    // hvaLogger initialization
    hvaLogger.setLogLevel(hva::hvaLogger_t::LogLevel::DISABLED);
    hvaLogger.enableProfiling();
    hva::hvaNodeRegistry::getInstance().init(HVA_NODE_REGISTRY_NO_DLCLOSE | HVA_NODE_REGISTRY_RTLD_GLOBAL);

    // read from config_file
    std::string contents;
    std::ifstream in(config_file, std::ios::in);
    if (in){
        in.seekg(0, std::ios::end);
        contents.resize(in.tellg());
        in.seekg(0, std::ios::beg);
        in.read(&contents[0], contents.size());
        in.close();
    }
    else {
        return false;
    }

    // parse pipeline parameters from config_str, generate the prepared pipeline
    hva::hvaPipelineParser_t parser;
    parser.parseFromString(contents, *pl);

    if (pl) {
        return true;
    }
    return false;
}

/**
 * @brief start inference
 * @param pl prepared pipeline
 * @param inputs images to process
 * 
 * @return boolean on success status
*/
bool doInference(const std::shared_ptr<hva::hvaPipeline_t>& pl, const std::vector<std::string>& inputs) {

    if (!pl) {
        HVA_ERROR("invalid pipeline!");
        return false;
    }

    if (inputs.size() == 0) {
        HVA_ERROR("empty inputs!");
        return false;
    }

    // define replyListener to capture the inference output
    boost::object_pool<_gtestReplyListener> rrlPool;
    std::shared_ptr<_gtestReplyListener> listener(rrlPool.construct(pl), [&](_gtestReplyListener* ptr){});
    if (!listener) {
        HVA_ERROR("register listener failed!");
        return false;   
    }

    try {
        // register replyListener in output node
        dynamic_cast<baseResponseNode&>(pl->getNodeHandle("Output")).registerEmitListener(std::move(listener));

        pl->prepare();

        HVA_INFO("Pipeline Start: ");
        pl->start();

        // prepare blob data, send to input node for inference
        auto blob = hva::hvaBlob_t::make_blob();
        if (blob) {
            blob->emplace<hva::hvaBuf_t>(inputs, sizeof(inputs));
            pl->sendToPort(blob, "Input", 0, std::chrono::milliseconds(0));
        }
        else {
            HVA_ERROR("empty blob!");
            return false;
        }
        
        // pipeline need time to consume all inputs and then transit to `idle`
        while (!g_finishTask) {
            HVA_INFO("sleeping till all tasks done");
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }

        // stop pipeline, tear down contexts
        HVA_INFO("going to stop");
        pl->stop();
        HVA_INFO("hva pipeline stopped.");
    }
    catch (...) {
        // explicitly catch all exceptions thrown by ai_inference service
        HVA_ERROR("pipeline inference failed!");
        return false;   
    }

    return true;
}

/**
 * @brief test ai node
 * @param pl prepared pipeline, only contains AI node and output node
 * @param inputs images to process
 * 
 * @return boolean on success status
*/
bool testAiNode(const std::shared_ptr<hva::hvaPipeline_t>& pl, const std::vector<std::string>& inputs) {
    
    if (!pl) {
        HVA_ERROR("invalid pipeline!");
        return false;
    }

    if (inputs.size() == 0) {
        HVA_ERROR("empty inputs!");
        return false;
    }

    // define replyListener to capture the inference output
    boost::object_pool<_gtestReplyListener> rrlPool;
    std::shared_ptr<_gtestReplyListener> listener(rrlPool.construct(pl), [&](_gtestReplyListener* ptr){});
    if (!listener) {
        HVA_ERROR("register listener failed!");
        return false;   
    }

    try {
        // register replyListener in output node
        dynamic_cast<baseResponseNode&>(pl->getNodeHandle("Output")).registerEmitListener(std::move(listener));

        pl->prepare();

        HVA_INFO("Pipeline Start: ");
        pl->start();
        unsigned frameIdx = 0;
        for (size_t b_ix = 0; b_ix < inputs.size(); b_ix ++) {

            std::string path = inputs[b_ix];
            HVA_DEBUG("reading image path: %s", path.c_str());
            cv::Mat decodedImage = cv::imread(path, cv::ImreadModes::IMREAD_COLOR);

            unsigned width = decodedImage.size().width;
            unsigned height = decodedImage.size().height;
            unsigned channel = decodedImage.channels();

            HVA_DEBUG("Input image at width: %d, height: %d and channel: %d", width, height, channel);
            std::string toSend((char*)decodedImage.data, width*height*channel);
            hva::hvaVideoFrameWithROIBuf_t::Ptr hvabuf =
                        hva::hvaVideoFrameWithROIBuf_t::make_buffer<uint8_t*>(
                            (uint8_t *)toSend.c_str(), toSend.size());
            
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

            if (b_ix == inputs.size()-1) {
                // last one in the batch. Mark it
                HVA_DEBUG("Set tag 1 on frame %d", frameIdx);
                hvabuf->tagAs(1);
            }
            else{
                hvabuf->tagAs(0);
            }
            HceDatabaseMeta meta;
            meta.bufType = HceDataMetaBufType::BUFTYPE_UINT8;
            hvabuf->setMeta(meta);            
            auto jpegBlob = hva::hvaBlob_t::make_blob();
            if (jpegBlob) {
                jpegBlob->frameId = frameIdx;
                jpegBlob->push(hvabuf);
                frameIdx ++;
                pl->sendToPort(jpegBlob, "Input", 0, std::chrono::milliseconds(0));
            }
            else {
                HVA_ERROR("empty blob!");
                return false;
            }
        }

        // pipeline need time to consume all inputs and then transit to `idle`
        while (!g_finishTask) {
            HVA_INFO("sleeping till all tasks done");
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }

        // stop pipeline, tear down contexts
        HVA_INFO("going to stop");
        pl->stop();
        HVA_INFO("hva pipeline stopped.");
    }
    catch (...) {
        // explicitly catch all exceptions thrown by ai_inference service
        HVA_ERROR("pipeline inference failed!");
        return false;   
    }

    return true;
}

/**
 * @brief Construct the LOADLOCALDATA TEST object
 * [TestCase-1]
 * Description UT:
 *  Load images from directory: ${HCE-REPO}/middleware/ai/ai_inference/test/demo
 */
TEST(AiPipelineTest, LOADLOCALDATA) {
    std::vector<std::string> inputs;
    EXPECT_EQ(true, loadLocalData(inputs));
}

/**
 * @brief Construct the LOADLOCALDATA TEST object on video pipeline
 * [TestCase-1]
 * Description UT:
 *  Load video from path: ${HCE-REPO}/middleware/ai/ai_inference/test/demo/road_barrier_1920_1080.h264
 */
TEST(AiVideoPipelineTest, LOADLOCALDATA) {
    std::vector<std::string> inputs;
    EXPECT_EQ(true, loadLocalVideoData(inputs));
}


/**
 * @brief Construct the PREPAREPIPELINE TEST object
 * [TestCase-2]
 * Description UT:
 *  Construct pipeline using configure:
 *      ${HCE-REPO}/middleware/ai/ai_inference/test/configs/cpuLocalImageAiPipeline.json 
 */
TEST(AiPipelineTest, PREPAREPIPELINE) {
    
    // specific configure: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/cpuLocalImageAiPipeline.json
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    std::string config_file = folder.string() + "/configs/cpuLocalImageAiPipeline.json";

    std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
    EXPECT_EQ(true, preparePipeline(pl, config_file));
}


/**
 * @brief Construct the PREPAREPIPELINE TEST object on video pipeline
 * [TestCase-2]
 * Description UT:
 *  Construct pipeline using configure:
 *      ${HCE-REPO}/middleware/ai/ai_inference/test/configs/cpuLocalVideoAiPipeline.json 
 */
TEST(AiVideoPipelineTest, PREPAREPIPELINE) {
    
    // specific configure: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/cpuLocalVideoAiPipeline.json
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    std::string config_file = folder.string() + "/configs/cpuLocalVideoAiPipeline.json";

    std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
    EXPECT_EQ(true, preparePipeline(pl, config_file));
}


/**
 * @brief Construct the DOINFERENCE TEST object
 * [TestCase-3]
 * Description UT:
 *      Localfile path -> JpegDecode -> VehicleDetection -> \
 *      VehicleAttribute(color & type) -> VehicleFeatureExtraction -> Output
 */
TEST(AiPipelineTest, DOINFERENCE) {

    // prepare data
    std::vector<std::string> inputs;
    loadLocalData(inputs);
    ASSERT_TRUE(inputs.size() > 0);
  
    // prepare pipeline
    // specific configure: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/cpuLocalImageAiPipeline.json
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    std::string config_file = folder.string() + "/configs/cpuLocalImageAiPipeline.json";
    std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
    preparePipeline(pl, config_file);
    ASSERT_TRUE(pl);

    EXPECT_EQ(true, doInference(pl, inputs));
}
/**
 * @brief Construct the DOINFERENCE TEST object on video pipeline
 * [TestCase-4]
 * Description UT:
 *      Localfile path -> VideoDecode -> VehicleDetection -> Tracker -> QualityAssess -> ObjectSelect -> \
 *      VehicleAttribute(color & type) -> VehicleFeatureExtraction -> Output
 */
TEST(AiVideoPipelineTest, DOINFERENCE) {

    // prepare data
    std::vector<std::string> inputs;
    loadLocalVideoData(inputs);
    ASSERT_TRUE(inputs.size() > 0);
  
    // prepare pipeline
    // specific configure: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/cpuLocalVideoAiPipeline.json
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    std::string config_file = folder.string() + "/configs/cpuLocalVideoAiPipeline.json";
    std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
    preparePipeline(pl, config_file);
    ASSERT_TRUE(pl);

    EXPECT_EQ(true, doInference(pl, inputs));
}

/**
 * @brief Construct the TESTAINODE TEST object on UTDetection
 * [TestCase-5]
 *   files are located in: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/unit_tests/
 *      [1] UTcpuDetection-barrier-0106.json
 *      [2] UTcpuDetection-crossroad-1016.json
 *      [3] UTcpuDetection-tiny-yolov2.json
 *      [4] UTcpuDetection-vehicle-evi001.json
 *      [5] UTcpuDetection-yolov3-1020.json
 * 
 */
TEST(DetectionNodeTest, DOINFERENCE) {

    // prepare data
    std::vector<std::string> inputs;
    loadLocalData(inputs);
    ASSERT_TRUE(inputs.size() > 0);

    // list all ai node UT
    std::vector<std::string> config_files = {
        "/configs/unit_tests/UTcpuDetection-barrier-0106.json",
        "/configs/unit_tests/UTcpuDetection-crossroad-1016.json",
        "/configs/unit_tests/UTcpuDetection-tiny-yolov2.json",
        "/configs/unit_tests/UTcpuDetection-vehicle-evi001.json",
        "/configs/unit_tests/UTcpuDetection-yolov3-1020.json"};

    // prepare pipeline
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    for (std::string path : config_files) {
        std::string config_file = folder.string() + path;
        std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
        preparePipeline(pl, config_file);
        ASSERT_TRUE(pl);

        EXPECT_EQ(true, doInference(pl, inputs));

        printf("Test DetectionNode pass, using: %s\n", path.c_str());
    }
}

/**
 * @brief Construct the TESTAINODE TEST object on UTClassification
 * [TestCase-6]
 *   files are located in: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/unit_tests/
 *      [1] UTcpuAttribute-barrier-0039.json
 *      [2] UTcpuAttribute-barrier-0042.json
 *      [3] UTcpuClassification-resnet18.json
 *      [4] UTcpuClassification-resnet34.json
 *      [5] UTcpuClassification-resnet50.json
 * 
 */
TEST(ClassificationNodeTest, DOINFERENCE) {

    // prepare data
    std::vector<std::string> inputs;
    loadLocalData(inputs);
    ASSERT_TRUE(inputs.size() > 0);

    // list all ai node UT
    std::vector<std::string> config_files = {
        "/configs/unit_tests/UTcpuAttribute-barrier-0039.json",
        "/configs/unit_tests/UTcpuAttribute-barrier-0042.json",
        "/configs/unit_tests/UTcpuClassification-resnet18.json",
        "/configs/unit_tests/UTcpuClassification-resnet34.json",
        "/configs/unit_tests/UTcpuClassification-resnet50.json"};

    // prepare pipeline
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    for (std::string path : config_files) {
        std::string config_file = folder.string() + path;
        std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
        preparePipeline(pl, config_file);
        ASSERT_TRUE(pl);

        EXPECT_EQ(true, doInference(pl, inputs));
        printf("Test ClassificationNode pass, using: %s\n", path.c_str());
    }
}

/**
 * @brief Construct the TESTAINODE TEST object on UTFeatureExtraction
 * [TestCase-7]
 *   files are located in: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/unit_tests/
 *      [1] UTcpuFeatureExtraction.json
 * 
 */
TEST(FeatureExtractionNodeTest, DOINFERENCE) {

    // prepare data
    std::vector<std::string> inputs;
    loadLocalData(inputs);
    ASSERT_TRUE(inputs.size() > 0);

    // list all ai node UT
    std::vector<std::string> config_files = {
        "/configs/unit_tests/UTcpuFeatureExtraction.json"};

    // prepare pipeline
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    for (std::string path : config_files) {
        std::string config_file = folder.string() + path;
        std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
        preparePipeline(pl, config_file);
        ASSERT_TRUE(pl);

        EXPECT_EQ(true, doInference(pl, inputs));
        printf("Test FeatureExtractionNode pass, using: %s\n", path.c_str());
    }
}

/**
 * @brief Construct the TESTAINODE TEST object on UTQuality
 * [TestCase-8]
 *   files are located in: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/unit_tests/
 *      [1] UTcpuQuality-blur.json
 *      [2] UTcpuQuality-qnet001.json
 *      [3] UTcpuQuality-random.json
 * 
 */
TEST(ObjectQualityNodeTest, DOINFERENCE) {

    // prepare data
    std::vector<std::string> inputs;
    loadLocalData(inputs);
    ASSERT_TRUE(inputs.size() > 0);

    // list all ai node UT
    std::vector<std::string> config_files = {
        "/configs/unit_tests/UTcpuQuality-blur.json",
        "/configs/unit_tests/UTcpuQuality-qnet001.json",
        "/configs/unit_tests/UTcpuQuality-random.json"};

    // prepare pipeline
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    for (std::string path : config_files) {
        std::string config_file = folder.string() + path;
        std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
        preparePipeline(pl, config_file);
        ASSERT_TRUE(pl);

        EXPECT_EQ(true, doInference(pl, inputs));
        printf("Test ObjectQualityNode pass, using: %s\n", path.c_str());
    }
}
/**
 * @brief Construct the TESTAINODE TEST object on UTtracker
 * [TestCase-9]
 *   files are located in: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/unit_tests/
 *      [1] UTcpuTracker-st-imageless.json
 *      [2] UTcpuTracker-zt-hist.json
 *      [3] UTcpuTracker-zt-imageless.json
 * 
 */
TEST(TrackerNodeTest, DOINFERENCE) {

    // prepare data
    std::vector<std::string> inputs;
    loadLocalData(inputs);
    ASSERT_TRUE(inputs.size() > 0);

    // list all ai node UT
    std::vector<std::string> config_files = {
        "/configs/unit_tests/UTcpuTracker-st-imageless.json",
        "/configs/unit_tests/UTcpuTracker-zt-hist.json",
        "/configs/unit_tests/UTcpuTracker-zt-imageless.json"};

    // prepare pipeline
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    for (std::string path : config_files) {
        std::string config_file = folder.string() + path;
        std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
        preparePipeline(pl, config_file);
        ASSERT_TRUE(pl);

        EXPECT_EQ(true, doInference(pl, inputs));
        printf("Test TrackerNode pass, using: %s\n", path.c_str());
    }
}

#ifdef ENABLE_VAAPI
TEST(AiPipelineTestGPU, DOINFERENCE) {

    // prepare data
    std::vector<std::string> inputs;
    loadLocalData(inputs);
    ASSERT_TRUE(inputs.size() > 0);
  
    // prepare pipeline
    // specific configure: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/cpuLocalImageAiPipeline.json
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    std::string config_file = folder.string() + "/configs/gpuLocalImageAiPipeline.json";
    std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
    preparePipeline(pl, config_file);
    ASSERT_TRUE(pl);

    EXPECT_EQ(true, doInference(pl, inputs));
}

TEST(AiVideoPipelineTestGPU, DOINFERENCE) {

    // prepare data
    std::vector<std::string> inputs;
    loadLocalVideoData(inputs);
    ASSERT_TRUE(inputs.size() > 0);
  
    // prepare pipeline
    // specific configure: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/cpuLocalVideoAiPipeline.json
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    std::string config_file = folder.string() + "/configs/gpuLocalVideoAiPipeline.json";
    std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
    preparePipeline(pl, config_file);
    ASSERT_TRUE(pl);

    EXPECT_EQ(true, doInference(pl, inputs));
}

TEST(DetectionNodeTestGPU, DOINFERENCE) {

    // prepare data
    std::vector<std::string> inputs;
    loadLocalData(inputs);
    ASSERT_TRUE(inputs.size() > 0);

    // list all ai node UT
    std::vector<std::string> config_files = {
        "/configs/unit_tests/UTgpuDetection-barrier-0106.json",
        "/configs/unit_tests/UTgpuDetection-crossroad-1016.json",
        "/configs/unit_tests/UTgpuDetection-tiny-yolov2.json",
        "/configs/unit_tests/UTgpuDetection-vehicle-evi001.json",
        "/configs/unit_tests/UTgpuDetection-yolov3-1020.json"};
  
    // prepare pipeline
    // specific configure: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/cpuLocalImageAiPipeline.json
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    for (std::string path : config_files) {
        printf("Test DetectionNodeTestGPU start, using: %s\n", path.c_str());
        std::string config_file = folder.string() + path;
        std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
        preparePipeline(pl, config_file);
        ASSERT_TRUE(pl);

        EXPECT_EQ(true, doInference(pl, inputs));
        printf("Test DetectionNodeTestGPU pass, using: %s\n", path.c_str());
    }    
}

TEST(ClassificationNodeTestGPU, DOINFERENCE) {

    // prepare data
    std::vector<std::string> inputs;
    loadLocalData(inputs);
    ASSERT_TRUE(inputs.size() > 0);

    // list all ai node UT
    std::vector<std::string> config_files = {
        "/configs/unit_tests/UTgpuAttribute-barrier-0039.json",
        "/configs/unit_tests/UTgpuAttribute-barrier-0042.json",
        "/configs/unit_tests/UTgpuClassification-resnet18.json",
        "/configs/unit_tests/UTgpuClassification-resnet34.json",
        "/configs/unit_tests/UTgpuClassification-resnet50.json"};
  
    // prepare pipeline
    // specific configure: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/cpuLocalImageAiPipeline.json
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    for (std::string path : config_files) {
        printf("Test ClassificationNodeTestGPU start, using: %s\n", path.c_str());
        std::string config_file = folder.string() + path;
        std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
        preparePipeline(pl, config_file);
        ASSERT_TRUE(pl);

        EXPECT_EQ(true, doInference(pl, inputs));
        printf("Test ClassificationNodeTestGPU pass, using: %s\n", path.c_str());
    }    
}

TEST(FeatureExtractionNodeTestGPU, DOINFERENCE) {

    // prepare data
    std::vector<std::string> inputs;
    loadLocalData(inputs);
    ASSERT_TRUE(inputs.size() > 0);

    // list all ai node UT
    std::vector<std::string> config_files = {
        "/configs/unit_tests/UTgpuFeatureExtraction.json"};

    // prepare pipeline
    // specific configure: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/cpuLocalImageAiPipeline.json
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    for (std::string path : config_files) {
        printf("Test FeatureExtractionNodeTestGPU start, using: %s\n", path.c_str());
        std::string config_file = folder.string() + path;
        std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
        preparePipeline(pl, config_file);
        ASSERT_TRUE(pl);

        EXPECT_EQ(true, doInference(pl, inputs));
        printf("Test FeatureExtractionNodeTestGPU pass, using: %s\n", path.c_str());
    }    
}

TEST(ObjectQualityNodeTestGPU, DOINFERENCE) {

    // prepare data
    std::vector<std::string> inputs;
    loadLocalData(inputs);
    ASSERT_TRUE(inputs.size() > 0);

    // list all ai node UT
    std::vector<std::string> config_files = {
        "/configs/unit_tests/UTgpuQuality-blur.json",
        "/configs/unit_tests/UTgpuQuality-qnet001.json",
        "/configs/unit_tests/UTgpuQuality-random.json"};

    // prepare pipeline
    // specific configure: ${HCE-REPO}/middleware/ai/ai_inference/test/configs/cpuLocalImageAiPipeline.json
    boost::filesystem::path p(__FILE__);
    boost::filesystem::path folder = p.parent_path();
    for (std::string path : config_files) {
        printf("Test ObjectQualityNodeTestGPU start, using: %s\n", path.c_str());
        std::string config_file = folder.string() + path;
        std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());
        preparePipeline(pl, config_file);
        ASSERT_TRUE(pl);

        EXPECT_EQ(true, doInference(pl, inputs));
        printf("Test ObjectQualityNodeTestGPU pass, using: %s\n", path.c_str());
    }    
}
#endif

int main(int argc, char** argv){

    // unit test using googletest
    printf("Running main() from %s\n", __FILE__);
    testing::InitGoogleTest(&argc, argv);

    return RUN_ALL_TESTS();
}

/**
 * @brief unit test summary
 * Unit test for doing inference on local image file, with vehicle structuring pipeline config:
 *   [image pipeline] Localfile path -> JpegDecode -> VehicleDetection \
 *                      -> VehicleAttribute(color & type) -> VehicleFeatureExtraction -> Output
 *   [video pipeline] Localfile path -> VideoDecode -> VehicleDetection -> Tracker -> QualityAssess -> ObjectSelect \
 *                      -> VehicleAttribute(color & type) -> VehicleFeatureExtraction -> Output
 *
 * @result description of unit test result
TestCase-1: load image files
TestCase-2: construct vehicle structuring pipeline
TestCase-3: use loaded images and the constructed pipeline to do inference
TestCase-4: use loaded video and the constructed pipeline to do inference
TestCase-5: use loaded images and the constructed pipeline to test ai node: DetectionNode
TestCase-6: use loaded images and the constructed pipeline to test ai node: ClassificationNode
TestCase-7: use loaded images and the constructed pipeline to test ai node: FeatureExtractionNode
TestCase-8: use loaded images and the constructed pipeline to test ai node: ObjectQualityNode
TestCase-9: use loaded images and the constructed pipeline to test ai node: TrackerNode
 * example output:
Running main() from /opt/hce-core/middleware/ai/ai_inference/test/gtestPipeline.cpp
[==========] Running 6 tests from 2 test suites.
[----------] Global test environment set-up.
[----------] 3 tests from AiPipelineTest
[ RUN      ] AiPipelineTest.LOADLOCALDATA
[       OK ] AiPipelineTest.LOADLOCALDATA (0 ms)
[ RUN      ] AiPipelineTest.PREPAREPIPELINE
Log level set to 0
Success to make attribute network
[       OK ] AiPipelineTest.PREPAREPIPELINE (776 ms)
[ RUN      ] AiPipelineTest.DOINFERENCE
Log level set to 0
Success to make attribute network
---------------------------------
 going to sleep for 30s
---------------------------------
Input #0, jpeg_pipe, from 'file':
  Duration: N/A, bitrate: N/A
    Stream #0:0: Video: mjpeg, yuvj420p(pc, bt470bg/unknown/unknown), 1920x1080, 25 tbr, 25 tbn, 25 tbc
[swscaler @ 0x7f27e0097d20] deprecated pixel format used, make sure you did set range correctly
process finished:
 {
    "result": [
        {
            "status_code": "0",
            "description": "succeeded"
        }
    ],
    "latency(ms)": "203",
    "frames": "1"
 }
[       OK ] AiPipelineTest.DOINFERENCE (31143 ms)
[----------] 3 tests from AiPipelineTest (32582 ms total)

[----------] 3 tests from AiVideoPipelineTest
[ RUN      ] AiVideoPipelineTest.LOADLOCALDATA
[       OK ] AiVideoPipelineTest.LOADLOCALDATA (0 ms)
[ RUN      ] AiVideoPipelineTest.PREPAREPIPELINE
Log level set to 1
Success to make attribute network
[       OK ] AiVideoPipelineTest.PREPAREPIPELINE (3122 ms)
[ RUN      ] AiVideoPipelineTest.DOINFERENCE
Log level set to 1
Success to make attribute network

---------------------------------
 going to sleep for 30s
---------------------------------
Input #0, h264, from 'file':
  Duration: N/A, bitrate: N/A
    Stream #0:0: Video: h264 (High), yuv420p(progressive), 1920x1080, 30 fps, 30 tbr, 1200k tbn, 60 tbc
process finished:
 {
    "result": [
        {
            "status_code": "1",
            "description": "noRoiDetected"
        },
        ...
    ],
    "latency(ms)": "4006",
    "frames": "17"
}
[       OK ] AiVideoPipelineTest.DOINFERENCE (33127 ms)
[----------] 3 tests from AiVideoPipelineTest (36249 ms total)

[----------] 1 test from DetectionNodeTest
[ RUN      ] DetectionNodeTest.TESTAINODE
[       OK ] DetectionNodeTest.TESTAINODE (51320 ms)
[----------] 1 test from DetectionNodeTest (51320 ms total)

[----------] 1 test from ClassificationNodeTest
[ RUN      ] ClassificationNodeTest.TESTAINODE
[       OK ] ClassificationNodeTest.TESTAINODE (50559 ms)
[----------] 1 test from ClassificationNodeTest (50559 ms total)

[----------] 1 test from FeatureExtractionNodeTest
[ RUN      ] FeatureExtractionNodeTest.TESTAINODE
[       OK ] FeatureExtractionNodeTest.TESTAINODE (10234 ms)
[----------] 1 test from FeatureExtractionNodeTest (10234 ms total)

[----------] 1 test from ObjectQualityNodeTest
[ RUN      ] ObjectQualityNodeTest.TESTAINODE
[       OK ] FeatureExtractionNodeTest.TESTAINODE (10234 ms)
[----------] 1 test from FeatureExtractionNodeTest (10234 ms total)

[----------] 1 test from ObjectQualityNodeTest
[ RUN      ] ObjectQualityNodeTest.TESTAINODE
[       OK ] ObjectQualityNodeTest.TESTAINODE (30152 ms)
[----------] 1 test from ObjectQualityNodeTest (30152 ms total)

[----------] 1 test from TrackerNodeTest
[ RUN      ] TrackerNodeTest.TESTAINODE
[       OK ] TrackerNodeTest.TESTAINODE (30054 ms)
[----------] 1 test from TrackerNodeTest (30054 ms total)

[----------] Global test environment tear-down
[==========] 11 tests from 7 test suites ran. (234339 ms total)
[  PASSED  ] 11 tests.

 */
