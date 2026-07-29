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

#include "utils/testUtils.hpp"
#include "nodes/base/baseResponseNode.hpp"
#include <inc/impl/hvaState.hpp>

#include <regex>
#include <cmath>
#include <sys/timeb.h>

using namespace hce::ai::inference;

std::vector<std::size_t> g_total;
std::vector<std::size_t> g_frameCnt;
size_t g_totalTasks;
std::mutex g_mutex;

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

        std::unique_lock<std::mutex> lk(m_mutex);

        // for sanity check
        if (!m_pl) {
            HCE_AI_ASSERT(false);
            HVA_ERROR("invalid pipeline!");
        }

        if(m_pl->getState() == hva::hvaState_t::running){
            
            // record results for each frame into m_frames
            boost::property_tree::ptree res_frame;
            std::stringstream ss(res.message); 
            boost::property_tree::read_json(ss, res_frame);
            m_frames.push_back(std::make_pair("", res_frame));
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

        std::unique_lock<std::mutex> lk(m_mutex);

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
            m_jsonTree.put("latency(ms)", latency);
            m_jsonTree.put("frames", m_frames.size() - m_accum_size);
            // m_jsonTree.put("fps", m_frames.size()*1000/latency);

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
    std::mutex m_mutex;                         // thread-safe
    boost::property_tree::ptree m_frames;
    uint64_t m_start;
    uint64_t m_accum_size;
    uint64_t m_burn;
};

int main(int argc, char** argv){

    try
    {

        // Check command line arguments.
        if(argc != 6 && argc != 7)
        {
            std::cerr <<
                "Usage: testMultiStreamAiPipeline <media_type> <configure_file> <data_path> <repeats> <total_stream_num> [<cross_stream_num>]\n" <<
                "Example:\n" <<
                "    ./testMultiStreamAiPipeline image ../../ai_inference/test/configs/cpuLocalImageAiPipeline.json /path/to/image_folder 1 8\n" <<
                "Or:\n" <<
                "    ./testMultiStreamAiPipeline image ../../ai_inference/test/configs/cross-stream/cpuLocalImageAiPipeline.json /path/to/image_folder 1 8 8\n" <<
                "Or:\n" <<
                "    ./testMultiStreamAiPipeline video ../../ai_inference/test/configs/cpuLocalVideoAiPipeline.json /path/to/video_path 1 8 \n" <<
                "Or:\n" <<
                "    ./testMultiStreamAiPipeline video ../../ai_inference/test/configs/cross-stream/cpuLocalVideoAiPipeline.json /path/to/video_folder 1 8 8\n" <<
                "------------------------------------------------------------------------------------------------- \n" <<
                "Environment requirement:\n" <<
                "   export HVA_NODE_DIR=/opt/hce-core/middleware/ai/build/lib \n" <<
                "   source /opt/intel/openvino*/setupvars.sh \n" <<
                "   source /opt/vpl_env.sh \n";
            return EXIT_FAILURE;
        }
        std::string media_type(argv[1]);
        std::string config_file(argv[2]);
        std::string data_path(argv[3]);
        unsigned repeats(atoi(argv[4]));
        unsigned total_stream_num(atoi(argv[5]));

        // optional args
        unsigned cross_stream_num = 1;
        if (argc == 7) {
            cross_stream_num = atoi(argv[6]);
        }
        unsigned threads = total_stream_num;

        // hvaLogger initialization
        hvaLogger.setLogLevel(hva::hvaLogger_t::LogLevel::DEBUG);
        hvaLogger.enableProfiling();
        hva::hvaNodeRegistry::getInstance().init(HVA_NODE_REGISTRY_NO_DLCLOSE | HVA_NODE_REGISTRY_RTLD_GLOBAL);

        std::vector<std::string> inputs; // paths of input files
        std::string mediaType;
        parseInputs(data_path, inputs, mediaType);

        // repeat inputs with total_streawm_num
        std::vector<std::string> repeat_inputs;
        for (int i = 0; i < total_stream_num; i++) {
            repeat_inputs.insert(repeat_inputs.end(), inputs.begin(), inputs.end());
        }

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
        // configure cross-batch style pipeline
        if (contents.find("stream_placeholder") != std::string::npos) {
            std::cout << "modify input config file to support cross-stream inference" << std::endl;
            contents = std::regex_replace(contents, std::regex("stream_placeholder"), std::to_string(cross_stream_num));
        }
        else if (cross_stream_num > 1) {
            std::cout << "pipelineConfig do not contain `stream_placeholder`, "
                        "request parameter: `cross_stream_num` will not take effect, "
                        "revert cross_stream_num to 1!"
                        << std::endl;
            cross_stream_num = 1;
        }
        std::cout << contents << std::endl;

        if (cross_stream_num > 1) {
            // batch streams together
            if (repeat_inputs.size() < cross_stream_num) {
                for (int i = repeat_inputs.size(); i<cross_stream_num; i++) {
                    repeat_inputs.push_back(repeat_inputs[0]);
                }
                // std::cerr << "Input mediaUris should be no less than the cross_stream_num!" << std::endl;
                // return EXIT_FAILURE;
            }
            
            threads = std::ceil(threads / cross_stream_num);
        }

        {
            std::lock_guard<std::mutex> lg(g_mutex);
            g_total.clear();
            g_frameCnt.clear();

            g_totalTasks = threads*repeats;
        }

        // construct pipelines
        std::vector<std::shared_ptr<hva::hvaPipeline_t>> pls;
        for(unsigned i = 0; i < threads; ++i){
            hva::hvaPipelineParser_t parser;
            std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());

            // construct pipeline
            std::cout << "start to construct pipeline: " << std::endl;
            std::cout << contents << std::endl;
            parser.parseFromString(contents, *pl);
            if (!pl) {
                // HVA_ERROR("fail to construct pipeline at %d!", i);
                HVA_ASSERT(false);
            }
      
            pl->prepare();

            HVA_INFO("Pipeline Start: ");
            pl->start();

            pls.push_back(pl);

        }

        // define replyListener to capture the inference output
        for(unsigned i = 0; i < threads; ++i){
            std::shared_ptr<_mtestReplyListener> listener = std::make_shared<_mtestReplyListener>(pls[i]);
            if (!listener) {
                HVA_ERROR("register listener failed!");
                return false;   
            }
            dynamic_cast<baseResponseNode&>(pls[i]->getNodeHandle("Output")).registerEmitListener(std::move(listener));
        }

        // repeat ai_inference process
        for(unsigned cnt =0; cnt < repeats; ++cnt){
            for (unsigned i = 0; i < threads; ++i) {

                // support cross-stream style pipeline config
                int segNum = std::floor(repeat_inputs.size() / cross_stream_num);
                for (unsigned streamId = 0; streamId < cross_stream_num; ++streamId) {

                    // get piece for cur streamId
                    int beginIndex = (int)streamId * segNum;
                    int endIndex = streamId == (cross_stream_num - 1) ? (int)repeat_inputs.size() : beginIndex + segNum;
                    std::vector<std::string> curInputs(repeat_inputs.begin() + beginIndex, repeat_inputs.begin() + endIndex);
                    
                    auto blob = hva::hvaBlob_t::make_blob();
                    blob->streamId = streamId;
                    blob->emplace<hva::hvaBuf_t>(curInputs, sizeof(curInputs));
                    pls[i]->sendToPort(blob, "Input", 0, std::chrono::milliseconds(0));
                }
            }
        }

        //
        // wait till pipeline consuming all input frames
        // this is the maximum processing time as estimated, not stand for the real duration.
        // pipeline need time to consume all inputs and then transit to `idle`
        //
        // int estimate_latency = std::max(30, int(0.1 * mediaVector.size()));  // 100ms for each image
        // if (media_type == "video") {
        //     estimate_latency = std::max(30, int(0.1 * mediaVector.size() * 300));  // assume 300 frames
        // }
        // HVA_INFO("going to sleep for %d s", estimate_latency);
        // std::this_thread::sleep_for(std::chrono::seconds(estimate_latency));

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
        float totalVideos = (float)total_stream_num * repeats;
        std::cout << totalVideos << " videos have been processed, including " << totalFrames << " frames" << std::endl;
        std::cout << "fps per stream: " << fps << std::endl;
    

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
            "feature_vector": "FxUKDvMO6fAYDPjp\/wkC\/Aj3AgD9EP4BC\/r++wjn\/\/wX9Av6\/gIC5\/H6B9z7ofYUBhEDAxDU\/+LyBunvHP\/3Dhb5\/RDsFP37\/vUdBwstCwjkBAAP9vgL4BIP9eHo\/wXj+QES2QYDAvjf\/\/8m\/\/H82xEE+vvN6
    w75EhUDDeoG9v\/u+PvnE+AqGO0P+eoEIgAuAOz1HAnuBAcHBwbu0Qb9FAwAJvH9BQP4JwEO+dQj+wH14BTw7CP+BAMI+BHZ\/xYK7f38\/\/sUAioK+xcX6f\/68gMDIwP39vUVAv0e\/QLw7O708vr+\/vH+Ch\/75O8n79nw+x\/xIewD\/QAB+ScfEPX\/DP0E6RH+Cu
    Xu7Pr8+fTpCPDV4O0I\/O0V9fwk9wgxBwT0+g\/3A\/gTCPsFFAsT8\/sg8vgCCdj39vgJ2BoJCegL+AgU7v7l\/x3nJAT1EAPx5fcaEgYH\/gzpIvwOABTw\/A7nFwUL7f3tARcAFBsFAN32AgAFCPruEOf56w3\/9f3vDQDu+RIRAP79\/AX\/9fEQEA4K4AT2+A8OBgMM
    9RUL9+D\/Ah4E7+z5CfgJ8B0YEAEM8QMC\/wjnGPwXCer+FP\/z+gbv+e32Aw339eP36gr9AAzpFtQq\/QYRDQUVFRFA7RT9BRj4JQ\/09A4UJgXtAv\/29QwFBA4pAw728TD97hntBBPsBf0=",
            "roi_class": "vehicle",
            "roi_score": "0.93460416793823242",
            "track_id": "0",
            "track_status": "0",
            "attribute": {
                "color": "white",
                "color_score": "0.998710513",
                "type": "van",
                "type_score": "0.99568969"
            },
            "license_plate": "<Yunnan>272"
        }
    ]
}
 on frame id 1

*/
