/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2024 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/


#include "nodes/base/baseResponseNode.hpp"
// #include <inc/impl/hvaState.hpp>

#include "utils/testUtils.hpp"
#include <sys/timeb.h>
#include <chrono>
#include <numeric>

// #include "nodes/databaseMeta.hpp"
// #include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>
// #include "modules/inference_util/radar/radar_detection_helper.hpp"

#include <sys/timeb.h>

using namespace hce::ai::inference;

std::vector<std::size_t> g_total;
std::vector<std::size_t> g_frameCnt;
size_t g_totalTasks;
std::mutex g_mutex;
std::vector<double> g_latency;

/**
 * @brief parse input local file
 */
void parseInputs(const std::string data_path, std::vector<std::string> &inputs, std::string &mediaType)
{
    if (boost::filesystem::exists(data_path)) {
        // is regular file
        if (boost::filesystem::is_directory(data_path)) {
            // use case:
            // multi-sensor inputs, organized as [bgr, radar, depth]

            if (!checkIsFolder(data_path)) {
                HVA_ERROR("path should be valid folder: %s", data_path.c_str());
                HVA_ASSERT(false);
            }

            std::vector<std::string> bgrInputs;
            getAllFiles(data_path + "/bgr", bgrInputs, ".bin");
            std::vector<std::string> radarInputs;
            getAllFiles(data_path + "/radar", radarInputs, ".bin");

            if (bgrInputs.size() != radarInputs.size()) {
                HVA_ERROR("each sensor input should have equal sizes, but got bgr: %d, radar: %d", bgrInputs.size(), radarInputs.size());
                HVA_ASSERT(false);
            }
            std::string path;
            // insert aligned sensor data by sequence
            for (int i = 0; i < radarInputs.size(); i++) {
                path = parseAbsolutePath(bgrInputs[i]);
                inputs.push_back(path);
                path = parseAbsolutePath(radarInputs[i]);
                inputs.push_back(path);
            }

            mediaType = "multisensor";
            std::cout << "Load " << inputs.size() << " files from folder: " << data_path.c_str() << ", mark media type as: " << mediaType << std::endl;
        }
        else {
            std::cerr << "Unknown data_path is specified: " << data_path.c_str() << ", it's neither regular file nor a directory, please check!" << std::endl;
            HVA_ASSERT(false);
        }
    }
    else {
        std::cerr << "File not exists: " << data_path.c_str() << std::endl;
        HVA_ASSERT(false);
    }
}

class _mtestReplyListener: public baseResponseNode::EmitListener{
public:
    _mtestReplyListener(std::shared_ptr<hva::hvaPipeline_t> pl)
            :baseResponseNode::EmitListener(), m_pl(pl) {

                // record the starting time
                m_start = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
                m_accum_size = 0;
                m_burn = 0;

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
            double latency;

            //get latency from jsonMessage for radar unit test
            latency = m_frame.get<double>("latency");
            g_latency.push_back(latency);

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
            // m_jsonTree.add_child("result", m_frames);
            m_jsonTree.put("Time usage(ms)", latency);
            m_jsonTree.put("frames", m_frames.size() - m_accum_size);
            m_jsonTree.put("fps", (m_frames.size()- m_accum_size)*1000/latency);

            std::stringstream ss;
            boost::property_tree::json_parser::write_json(ss, m_jsonTree);
            printf("process finished:\n %s", ss.str().c_str());

            if (m_burn == 0) {
                std::lock_guard<std::mutex> lg(g_mutex);
                g_total.push_back(latency);
                g_frameCnt.push_back(m_frames.size() - m_accum_size);
                g_totalTasks --;
            } else {
                m_burn --;
                std::lock_guard<std::mutex> lg(g_mutex);
                g_totalTasks --;
            }

            // refresh the starting time
            m_accum_size = m_frames.size();
            m_start = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();

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
    uint64_t m_accum_size;
    uint64_t m_burn;
};

int main(int argc, char** argv){

    try
    {

        // Check command line arguments.
        if(argc != 4)
        {
            std::cerr <<
                "Usage: testRadarPerformance <configure_file> <data_path> <repeats> \n" <<
                "Example:\n" <<
                "    testRadarPerformance ../../ai_inference/test/configs/raddet/1C1R/localRadarPipeline.json /path/to/dataset 1 \n" <<
                "------------------------------------------------------------------------------------------------- \n" <<
                "Environment requirement:\n" <<
                "   export HVA_NODE_DIR=$PWD/build/lib \n" <<
                "   source /opt/intel/oneapi/setvars.sh \n" <<
                "   source /opt/intel/openvino*/setupvars.sh \n";
  
            return EXIT_FAILURE;
        }

        std::string config_file(argv[1]);
        std::string data_path(argv[2]);
        unsigned repeats(atoi(argv[3]));

        // hvaLogger initialization
        hvaLogger.setLogLevel(hva::hvaLogger_t::LogLevel::ERROR);
        // hvaLogger initialization
        // hvaLogger.setLogLevel(hva::hvaLogger_t::LogLevel::DEBUG);
        // hvaLogger.enableProfiling();
        hva::hvaNodeRegistry::getInstance().init(HVA_NODE_REGISTRY_NO_DLCLOSE | HVA_NODE_REGISTRY_RTLD_GLOBAL);

        std::vector<std::string> inputs; // paths of input files
        std::string mediaType;
        parseInputs(data_path, inputs, mediaType);

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
            HVA_ERROR("invalid config file!");
            HVA_ASSERT(false);
        }

        {
            std::lock_guard<std::mutex> lg(g_mutex);
            g_total.clear();
            g_frameCnt.clear();
            g_totalTasks = repeats;
        }

        // construct pipelines
        std::vector<std::shared_ptr<hva::hvaPipeline_t>> pls;
        for(unsigned i = 0; i < 1; ++i){
            hva::hvaPipelineParser_t parser;
            std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());

            // construct pipeline
            parser.parseFromString(contents, *pl);
            if (!pl) {
                HVA_ERROR("fail to construct pipeline at %d!", i);
                HVA_ASSERT(false);
            }
    
            pl->prepare();

            HVA_INFO("Pipeline Start: ");
            pl->start();

            pls.push_back(pl);
        }

        // repeat ai_inference process
        for(unsigned cnt =0; cnt < repeats; ++cnt){
                auto blob = hva::hvaBlob_t::make_blob();
                if (blob) {
                    blob->emplace<hva::hvaBuf_t>(inputs, sizeof(inputs));
                    pls[0]->sendToPort(blob, "Input", 0, std::chrono::milliseconds(0));
                }
                else {
                    HVA_ERROR("empty blob!");
                    HVA_ASSERT(false);
                }

        }

        // define replyListener to capture the inference output
        std::shared_ptr<_mtestReplyListener> listener = std::make_shared<_mtestReplyListener>(pls[0]);
        if (!listener) {
            HVA_ERROR("register listener failed!");
            return false;   
        }
        dynamic_cast<baseResponseNode&>(pls[0]->getNodeHandle("Output")).registerEmitListener(std::move(listener));

        bool done = false;
        while (true) {
            {
                std::lock_guard<std::mutex> lg(g_mutex);
                done = g_totalTasks == 0;
            }
            if (done) {
                break;
            } else {
                HVA_INFO("sleeping till all tasks done");
                std::this_thread::sleep_for(std::chrono::seconds(1));
            }
        }
        
        // stop pipeline, tear down contexts
        HVA_INFO("going to stop");
        for(auto& item: pls){
            item->stop();
        }
        HVA_INFO("hva pipeline stopped.");

        // ---------------------------------------------------------------------------
        //                                 performance check
        //  ---------------------------------------------------------------------------
        float totalTime = 0;
        float inferLatency = 0;
        std::size_t totalFrames = 0;
        std::lock_guard<std::mutex> lg(g_mutex);
        std::cout<<"Time used by each thread: " << std::endl;
        for(std::size_t tix = 0; tix < g_total.size(); tix ++) {
            std::cout << g_frameCnt[tix] << "frames," << g_total[tix] << " ms" << std::endl;
            totalTime += g_total[tix];
            totalFrames += g_frameCnt[tix];
        }
        std::cout << "Total time: "<< totalTime << " ms"<<std::endl;

        float mean = totalTime / g_total.size();
        std::cout<<"Mean time: "<< mean << " ms"<<std::endl;

        std::cout << "\n=================================================\n" << std::endl;
        /* frames_each_stream / time_each_stream => fps_each_stream */
        float fps = ((float)totalFrames / g_total.size()) / (mean / 1000.0);
        float totalVideos = (float)repeats;
        std::cout << totalVideos << " videos have been processed, including " << totalFrames << " frames" << std::endl;
        std::cout << "fps per stream: " << fps << std::endl;
        double latency_sum = std::accumulate(std::begin(g_latency), std::end(g_latency), 0.0);
        double latency_ave =  latency_sum / g_latency.size();
        std::cout << "average latency " << latency_ave <<std::endl;
        std::cout << "\n=================================================\n" << std::endl;
    

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
   [INFO] [3660993] [1699515021089]: RadarOutputNode.cpp:145 process Emit: {
    "status_code": "0",
    "description": "succeeded",
    "roi_info": [
        {
            "roi": [
                "9.43721771",
                "-3.23720407",
                "-2.71280003",
                "0.929784358",
                "3.14976931",
                "1.4344734"
            ],
            "track_id": {
                "trackerID": "1"
            }
        }
    ]
}
 on frame id 5980

*/
