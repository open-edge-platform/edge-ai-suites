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
#include <chrono>
#include <mutex>

#include "low_latency_client/lowLatencyClient.hpp"

using namespace hce::ai::inference;

std::vector<std::size_t> g_total;
std::vector<std::size_t> g_frameCnt;
std::mutex g_mutex;

void workload(const std::string& host, const std::string& port, const std::string& json, const std::string& data_path, 
              unsigned repeats, const std::string& media_type, unsigned thread_id, unsigned stream_num){
    
    unsigned suggested_weight = 0;
    hce::ai::inference::LLHttpClient client{host, port};

    client.connect();
    std::chrono::time_point<std::chrono::high_resolution_clock> a, b;
    std::chrono::milliseconds timeUsed(0);
    std::chrono::milliseconds thisTime(0);
    std::size_t frameCnt(0);

    std::vector<std::string> mediaVector;

    if (!checkPathExist(data_path)) {
        std::cerr << "path not exists: " << data_path.c_str() << std::endl;
        HVA_ASSERT(false);
    }
    
    if (media_type == "image") {
        std::cout << "testLocalPipeline load images from folder: " << data_path.c_str() << std::endl;
        getAllFiles(data_path, mediaVector, ".jpg");
    }
    else if (media_type == "video") {

        if (checkRegularFile(data_path)) {
            std::cout << "testLocalPipeline load video file: " << data_path.c_str()<< std::endl;
            mediaVector.push_back(data_path);
        }
        else {
            std::cerr << "Not support for reading from folder for media_type: video!" << std::endl;
            HVA_ASSERT(false);
        }

    }
    else {
        std::cerr << "testLocalPipeline receive unknow media type: " << media_type.c_str() << std::endl;
    }

    std::vector<std::string> inputs;
    // repeat input media for `stream_num` times
    for (unsigned i = 0; i < stream_num; i ++) {
        inputs.insert(inputs.end(), mediaVector.begin(), mediaVector.end());
    }
    std::string info = "[thread " + std::to_string(thread_id) + "] Input media size is: " + std::to_string(inputs.size());
    std::cout << info << std::endl;

    for(unsigned i =0; i < repeats; ++i){
        unsigned retCode = 0;
        std::string ret;
        a = std::chrono::high_resolution_clock::now();
        client.run(json, inputs, retCode, ret, suggested_weight, stream_num);
        b = std::chrono::high_resolution_clock::now();
        thisTime = std::chrono::duration_cast<std::chrono::milliseconds>(b - a);
        timeUsed = thisTime + timeUsed;

        std::cout << retCode << std::endl;
        
        // parse ret results
        try {
            boost::property_tree::ptree jsonTree;
            std::stringstream ss(ret);
            boost::property_tree::json_parser::read_json(ss, jsonTree);
            const auto& resultsTree = jsonTree.get_child("result");
            frameCnt += resultsTree.size();

            std::cout << ret << std::endl;
            std::string info = "[thread " + std::to_string(thread_id) + "] " +  std::to_string(resultsTree.size()) + " frames been processed.";
            std::cout << info << std::endl;

        } catch (const boost::property_tree::ptree_error& e){
            std::cout << "Failed to read response ret: \n" << ret << std::endl;
        } catch (boost::exception& e){
            std::cout << "Failed to read response ret: \n" << ret << std::endl;
        }
    }

    client.shutdown();

    std::lock_guard<std::mutex> lg(g_mutex);
    g_total.push_back(timeUsed.count());
    g_frameCnt.push_back(frameCnt);

}

int main(int argc, char** argv){

    try
    {
        // Check command line arguments.
        if(argc != 8 && argc != 9)
        {
            std::cerr <<
                "Usage: testLocalPipeline <host> <port> <json_file> <total_stream_num> <repeats> <data_path> <media_type> [<cross_stream_num>]\n" <<
                "Example:\n" <<
                "    ./testLocalPipeline 127.0.0.1 50051 ../../ai_inference/test/configs/cpuLocalImageAiPipeline.json 1 10 /path/to/image_folder image\n" <<
                "Or:\n" <<
                "    ./testLocalPipeline 127.0.0.1 50051  ../../ai_inference/test/configs/cpuLocalVideoAiPipeline.json 1 10 /path/to/video_path video\n" <<
                "Or:\n" <<
                "    ./testLocalPipeline 127.0.0.1 50051 ../../ai_inference/test/configs/cross-stream/cpuLocalImageAiPipeline.json 1 10 /path/to/image_folder image 8\n" <<
                "Or:\n" <<
                "    ./testLocalPipeline 127.0.0.1 50051  ../../ai_inference/test/configs/cross-stream/cpuLocalVideoAiPipeline.json 1 10 /path/to/video_path video 8\n";
            return EXIT_FAILURE;
        }
        std::string host(argv[1]);
        std::string port(argv[2]);
        std::string jsonFile(argv[3]);
        unsigned totalStreamNum(atoi(argv[4]));
        unsigned repeats = atoi(argv[5]);
        std::string dataPath(argv[6]);
        std::string mediaType(argv[7]);

        // optional args
        unsigned crossStreamNum = 1;
        if (argc == 9) {
            crossStreamNum = atoi(argv[8]);
            // for sanity check
            if (totalStreamNum < crossStreamNum) {
                std::cerr << "total-stream-number should be no less than cross-stream-number!" << std::endl;
                return EXIT_FAILURE;
            }
            if (totalStreamNum / crossStreamNum * crossStreamNum != totalStreamNum) {
                std::cerr << "total-stream-number should be divisible by cross-stream-number!" << std::endl;
                return EXIT_FAILURE;
            }
        }
        unsigned threadNum = totalStreamNum / crossStreamNum;

        std::string contents;
        std::ifstream in(jsonFile, std::ios::in);
        if (in){
            in.seekg(0, std::ios::end);
            contents.resize(in.tellg());
            in.seekg(0, std::ios::beg);
            in.read(&contents[0], contents.size());
            in.close();
        }

        std::cout << "Start processing with " << threadNum
                  << " threads: total-stream = " << totalStreamNum
                  << ", each thread will process " << crossStreamNum << " streams" << std::endl;

        std::vector<std::thread> vThs;

        for(unsigned i =0; i < threadNum; ++i){
            std::thread t(workload, std::ref(host), std::ref(port), std::ref(contents), std::ref(dataPath), repeats, mediaType, i, crossStreamNum);
            vThs.push_back(std::move(t));
        }

        for(auto& item: vThs){
            item.join();
        }

        float totalTime = 0;
        std::size_t totalFrames = 0;
        std::lock_guard<std::mutex> lg(g_mutex);
        std::cout<<"Time used by each thread: " << std::endl;
        for(std::size_t tix = 0; tix < g_total.size(); tix ++) {
            std::cout << g_frameCnt[tix] << "frames," << g_total[tix] << " ms" << std::endl;
            totalTime += g_total[tix];
            totalFrames += g_frameCnt[tix];
        }
        std::cout << "Total time: "<< totalTime << " ms"<<std::endl;

        float totalRequests = (float)threadNum * repeats;
        float mean = totalTime / g_total.size();
        std::cout<<"Mean time: "<< mean << " ms"<<std::endl;        // mean time for each thread (include all repeats)
        float qps = totalRequests / (mean / 1000.0);
        std::cout << "\n qps: " << qps << std::endl;
        std::cout << "\n qps per stream: " << qps / totalStreamNum << std::endl;

        /* frames_each_stream / time_each_stream => fps_each_stream */
        float fps = ((float)totalFrames / totalStreamNum) / (mean / 1000.0);
        if (mediaType == "video") {
            // fps calculation for media_type: video
            std::cout << "\n=================================================\n" << std::endl;
            std::cout << "For each repeat: " << threadNum << " threads have been processed, total-stream = " << totalStreamNum
                  << ", each thread processed " << crossStreamNum << " streams" << std::endl;
            std::cout << "fps per stream: " << fps << ", including " << totalFrames << " frames" << std::endl;
            std::cout << "\n=================================================\n" << std::endl;
        }
        else if (mediaType == "image") {
            // imgs/sec calculation for media_type: image
            std::cout << "\n=================================================\n" << std::endl;
            std::cout << "For each repeat: " << threadNum << " threads have been processed, total-stream = " << totalStreamNum
                  << ", each thread processed " << crossStreamNum << " streams" << std::endl;
            std::cout << "images per second: " << fps * totalStreamNum << ", including " << totalFrames << " frames" << std::endl;
            std::cout << "\n=================================================\n" << std::endl;
        }

        return 0;
    }
    catch(std::exception const& e)
    {
        std::cerr << "Error: " << e.what() << std::endl;
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
