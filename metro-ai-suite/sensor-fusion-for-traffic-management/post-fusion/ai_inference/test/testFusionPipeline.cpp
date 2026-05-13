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

#include "utils/testUtils.hpp"
#include <sys/timeb.h>

using namespace hce::ai::inference;
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

int main(int argc, char **argv)
{
    try {
        // Check command line arguments.
        if (argc != 4) {
            std::cerr << "Usage: testFusionPipeline <configure_file> <data_path> <repeats> \n"
                      << "Example:\n"
                      << "    testFusionPipeline ../../ai_inference/test/configs/raddet/localFusionPipeline.json /path/to/dataset 1 \n"
                      << "------------------------------------------------------------------------------------------------- \n"
                      << "Environment requirement:\n"
                      << "   export HVA_NODE_DIR=$PWD/build/lib \n"
                      << "   source /opt/intel/oneapi/setvars.sh \n"
                      << "   source /opt/intel/openvino*/setupvars.sh \n";
            return EXIT_FAILURE;
        }
        std::string config_file(argv[1]);
        std::string data_path(argv[2]);
        unsigned repeats(atoi(argv[3]));

        // hvaLogger initialization
        hvaLogger.setLogLevel(hva::hvaLogger_t::LogLevel::DEBUG);
        hvaLogger.enableProfiling();
        hva::hvaNodeRegistry::getInstance().init(HVA_NODE_REGISTRY_NO_DLCLOSE | HVA_NODE_REGISTRY_RTLD_GLOBAL);

        // std::vector<std::string> inputs;
        // inputs.push_back(data_path);

        std::vector<std::string> inputs;  // paths of input bin files
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

        // construct pipelines
        std::vector<std::shared_ptr<hva::hvaPipeline_t>> pls;
        for (unsigned i = 0; i < 1; ++i) {
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
        for (unsigned cnt = 0; cnt < repeats; ++cnt) {
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
        //
        // wait till pipeline consuming all input frames
        // this is the maximum processing time as estimated, not stand for the real duration.
        // pipeline need time to consume all inputs and then transit to `idle`
        //
        int estimate_latency = repeats * 30;
        // if (media_type == "video") {
        //     estimate_latency = std::max(30, int(0.1 * mediaVector.size() * 300));  // assume 300 frames
        // }
        HVA_INFO("going to sleep for %d s", estimate_latency);
        std::this_thread::sleep_for(std::chrono::seconds(estimate_latency));

        // stop pipeline, tear down contexts
        HVA_INFO("going to stop");
        for (auto &item : pls) {
            item->stop();
        }
        HVA_INFO("hva pipeline stopped.");

        return 0;
    }
    catch (std::exception const &e) {
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
