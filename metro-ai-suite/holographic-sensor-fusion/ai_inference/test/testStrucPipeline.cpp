/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2022 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#include <cstdlib>
#include <iostream>
#include <string>
#include <cstdint>
#include <chrono>
#include <vector>
#include <thread>
#include <stdlib.h>
#include <time.h>
#include <iostream>
#include <sys/types.h>
#include <dirent.h>
#include <chrono>
#include <mutex>

#include "low_latency_client/lowLatencyClient.hpp"
#include "common/base64.hpp"

std::vector<std::size_t> g_total;
std::mutex g_mutex;

void workload(const std::string& host, const std::string& port, const std::string& json, std::vector<std::string>& image, unsigned repeats){

    hce::ai::inference::LLHttpClient client{host, port};

    client.connect();
    std::chrono::time_point<std::chrono::high_resolution_clock> a, b;
    std::chrono::milliseconds timeUsed(0);
    std::chrono::milliseconds thisTime(0);

    for(unsigned i =0; i < repeats; ++i){
        unsigned retCode = 0;
        std::string ret;
        a = std::chrono::high_resolution_clock::now();
        client.run(json, image, retCode, ret);
        b = std::chrono::high_resolution_clock::now();
        thisTime = std::chrono::duration_cast<std::chrono::milliseconds>(b - a);
        timeUsed = thisTime + timeUsed;

        std::cout << retCode << std::endl;
        std::cout << ret << std::endl;
    }

    client.shutdown();

    std::lock_guard<std::mutex> lg(g_mutex);
    g_total.push_back(timeUsed.count());

}

// Performs an HTTP GET and prints the response
int main(int argc, char** argv)
{
    try
    {
        // Check command line arguments.
        if(argc != 7)
        {
            std::cerr <<
                "Usage: testStrucPipeline <host> <port> <json_file> <thread_number> <repeats> <list_file> \n" <<
                "Example:\n" <<
                "    testStrucPipeline www.example.com 80 ./LLPipeline.json 1 10 /path/to/media_uri.list \n" <<
                "--------------------------------------------------------------------------------------- \n" <<
                "    You may need to modify list file: media_uri_*.list \n" <<
                "    Please make sure they exist in the media-storage \n";
            return EXIT_FAILURE;
        }
        std::string host(argv[1]);
        std::string port(argv[2]);
        int version = 11;
        std::string jsonFile(argv[3]);
        unsigned threadNum = atoi(argv[4]);
        unsigned repeats = atoi(argv[5]);
        std::string list_file(argv[6]);

        std::vector<std::thread> vThs;

        std::string contents;
        std::ifstream in(jsonFile, std::ios::in);
        if (in){
            in.seekg(0, std::ios::end);
            contents.resize(in.tellg());
            in.seekg(0, std::ios::beg);
            in.read(&contents[0], contents.size());
            in.close();
        }

        std::vector<std::string> imagesVector;
        std::string in_list;
        std::ifstream fin(list_file, std::ios::in);
        while (getline(fin, in_list)) {
            std::istringstream stringIn;
            stringIn.str(in_list);
		    imagesVector.push_back(stringIn.str());
        }
        fin.close();

        std::cout << "input " << imagesVector.size() << " media uris: " << std::endl;
        for (size_t i = 0; i < imagesVector.size(); i ++) {

            std::cout << imagesVector[i] << std::endl;
        }

        for(unsigned i =0; i < threadNum; ++i){
            std::thread t(workload, std::ref(host), std::ref(port), std::ref(contents), std::ref(imagesVector), repeats);
            vThs.push_back(std::move(t));
        }

        for(auto& item: vThs){
            item.join();
        }

        float total = 0;
        std::lock_guard<std::mutex> lg(g_mutex);
        std::cout<<"Time used by each thread: " << std::endl;
        for(const auto& item: g_total){
            std::cout<<item<<" ms" << std::endl;
            total += item;
        }
        std::cout<<"Total time: "<< total<< " ms"<<std::endl;

        float qps = ((float)threadNum*repeats)/(total/1000.0);
        std::cout<<"\n qps: "<<qps<<std::endl;

        return 0;
    }
    catch(std::exception const& e)
    {
        std::cerr << "Error: " << e.what() << std::endl;
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}

//]
