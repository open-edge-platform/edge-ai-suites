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
#include <inc/impl/hvaState.hpp>

#include "utils/testUtils.hpp"
#include <sys/timeb.h>
#include <chrono>
#include "nodes/databaseMeta.hpp"
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>
#include "modules/inference_util/radar/radar_detection_helper.hpp"

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
        if (boost::filesystem::is_regular_file(data_path)) {
            // use case:
            // single Hdf5 file as input

            if (!CheckPostFix(data_path, ".h5")) {
                std::cerr << "Unknown data_path is specified: " << data_path.c_str() << ", should be *.h5, please check!" << std::endl;
                HVA_ASSERT(false);
            }
            inputs.push_back(parseAbsolutePath(data_path));

            mediaType = "H5";
            std::cout << "Load input from file: " << data_path.c_str() << ", mark media type as: " << mediaType << std::endl;
        }
        else if (boost::filesystem::is_directory(data_path)) {
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

class _mtestReplyListener : public baseResponseNode::EmitListener {
  public:
    _mtestReplyListener(std::shared_ptr<hva::hvaPipeline_t> pl) : baseResponseNode::EmitListener(), m_pl(pl)
    {
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
    virtual void onEmit(baseResponseNode::Response res, const baseResponseNode *node, void *data) override
    {
        // for sanity check
        if (!m_pl) {
            HCE_AI_ASSERT(false);
            HVA_ERROR("invalid pipeline!");
        }

        if (m_pl->getState() == hva::hvaState_t::running) {
            // record results for each frame into m_frames
            m_frame.clear();
            std::stringstream ss(res.message);
            boost::property_tree::read_json(ss, m_frame);
            m_frames.push_back(std::make_pair("", m_frame));
        }
        else {
            // if not in running state, it may be abnormally interrupted
            HCE_AI_ASSERT(false);
            HVA_ERROR("Pipeline no longer exists at reply listener destruction");
        }
    };

    /**
     * @brief  reply to client after request frames all finished processing.
     * @param node outputNode who sends response here
     */
    virtual void onFinish(const baseResponseNode *node, void *data) override
    {
        // for sanity check
        if (!m_pl) {
            HCE_AI_ASSERT(false);
            HVA_ERROR("invalid pipeline!");
        }

        if (m_pl->getState() == hva::hvaState_t::running) {
            // latency for this inference process
            uint64_t end = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
            uint64_t latency = end - m_start;

            // construct final results as json-style str
            // m_jsonTree.add_child("result", m_frames);
            m_jsonTree.put("latency(ms)", latency);
            m_jsonTree.put("frames", m_frames.size() - m_accum_size);
            m_jsonTree.put("fps", (m_frames.size() - m_accum_size) * 1000 / latency);

            std::stringstream ss;
            boost::property_tree::json_parser::write_json(ss, m_jsonTree);
            printf("process finished:\n %s", ss.str().c_str());

            if (m_burn == 0) {
                std::lock_guard<std::mutex> lg(g_mutex);
                g_total.push_back(latency);
                g_frameCnt.push_back(m_frames.size() - m_accum_size);
                g_totalTasks--;
            }
            else {
                m_burn--;
                std::lock_guard<std::mutex> lg(g_mutex);
                g_totalTasks--;
            }

            // refresh the starting time
            m_accum_size = m_frames.size();
            m_start = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
        }
        else {
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

int main(int argc, char **argv)
{
    try {
        // Check command line arguments.
        if (argc != 5) {
            std::cerr << "Usage: testFusionPerformance <repeats> <streams> <configure_file> <data_path>\n"
                      << "Example:\n"
                      << "    testFusionPerformance 2 1 ../../ai_inference/test/configs/raddet/localFusionPipeline.json /path/to/dataset\n"
                      << "------------------------------------------------------------------------------------------------- \n"
                      << "Environment requirement:\n"
                      << "   export HVA_NODE_DIR=$PWD/build/lib \n"
                      << "   source /opt/intel/oneapi/setvars.sh \n"
                      << "   source /opt/intel/openvino*/setupvars.sh \n";

            return EXIT_FAILURE;
        }
        unsigned repeats(atoi(argv[1]));
        unsigned streams(atoi(argv[2]));
        std::string config_file(argv[3]);
        std::string data_path(argv[4]);

        // hvaLogger initialization
        // hvaLogger.setLogLevel(hva::hvaLogger_t::LogLevel::ERROR);
        hvaLogger.setLogLevel(hva::hvaLogger_t::LogLevel::ERROR);
        hvaLogger.enableProfiling();
        hva::hvaNodeRegistry::getInstance().init(HVA_NODE_REGISTRY_NO_DLCLOSE | HVA_NODE_REGISTRY_RTLD_GLOBAL);

        std::vector<std::string> inputs;  // paths of input files
        std::string mediaType;
        parseInputs(data_path, inputs, mediaType);

        // read from config_file
        std::string contents;
        std::ifstream in(config_file, std::ios::in);
        if (in) {
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
            g_totalTasks = streams * repeats;
        }

        // construct pipelines
        std::vector<std::shared_ptr<hva::hvaPipeline_t>> pls;
        for (unsigned i = 0; i < streams; ++i) {
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

        // define replyListener to capture the inference output
        for (unsigned i = 0; i < streams; ++i) {
            std::shared_ptr<_mtestReplyListener> listener = std::make_shared<_mtestReplyListener>(pls[i]);
            if (!listener) {
                HVA_ERROR("register listener failed!");
                return false;
            }
            dynamic_cast<baseResponseNode &>(pls[i]->getNodeHandle("Output")).registerEmitListener(std::move(listener));
        }
        // repeat ai_inference process
        // need include radar decode

        //    int  NX=10; // debug
        int accumIndex = 0;

        for (unsigned cnt = 0; cnt < repeats; ++cnt) {
            for (unsigned i = 0; i < streams; ++i) {
                auto blob = hva::hvaBlob_t::make_blob();

                if (blob) {
                    // blob->frameId = accumIndex + frame_index;
                    blob->emplace<hva::hvaBuf_t>(inputs, sizeof(inputs));
                    pls[i]->sendToPort(blob, "Input", 0, std::chrono::milliseconds(0));
                }
                else {
                    HVA_ERROR("empty blob!");
                    HVA_ASSERT(false);
                }
            }
        }
        bool done = false;
        while (true) {
            {
                std::lock_guard<std::mutex> lg(g_mutex);
                done = g_totalTasks == 0;
            }
            if (done) {
                break;
            }
            else {
                HVA_INFO("sleeping till all tasks done");
                std::this_thread::sleep_for(std::chrono::seconds(1));
            }
        }

        // stop pipeline, tear down contexts
        HVA_INFO("going to stop");
        for (auto &item : pls) {
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
        std::cout << "Time used by each thread: " << std::endl;
        for (std::size_t tix = 0; tix < g_total.size(); tix++) {
            std::cout << g_frameCnt[tix] << "frames," << g_total[tix] << " ms" << std::endl;
            totalTime += g_total[tix];
            totalFrames += g_frameCnt[tix];
        }
        std::cout << "Total time: " << totalTime << " ms" << std::endl;

        float mean = totalTime / g_total.size();
        std::cout << "Mean time: " << mean << " ms" << std::endl;

        std::cout << "\n=================================================\n" << std::endl;
        /* frames_each_stream / time_each_stream => fps_each_stream */
        float fps = ((float)totalFrames / g_total.size()) / (mean / 1000.0);
        float totalVideos = (float)repeats;
        std::cout << totalVideos << " videos have been processed, including " << totalFrames << " frames" << std::endl;
        std::cout << "fps per stream: " << fps << std::endl;


        return 0;
    }
    catch (std::exception const &e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
