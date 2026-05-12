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

    std::vector<std::string> inputs;
    for(const auto& item: image){
        inputs.push_back(hce::ai::inference::LLHttpClient::composeMediaInputWithROI(item, 0, 0, 0, 0));
    }

    for(unsigned i =0; i < repeats; ++i){
        unsigned retCode = 0;
        std::string ret;
        a = std::chrono::high_resolution_clock::now();
        client.run(json, inputs, retCode, ret);
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

bool CheckPostFix(char* pFileName)
{
    if (pFileName == nullptr)
    {
        return false;
    }
 
    std::string strFileName = pFileName;
    int nStartPos = strFileName.rfind(".");
    if (nStartPos == -1)
    {
        return false;
    }
 
    std::string strPostFix = strFileName.substr(strFileName.rfind("."));
 
    if (strPostFix.find(".jpg") == std::string::npos)
    {
        return false;
    }
 
    return true;
}

void readJpgToCharBuffer(const std::string& fileName, std::string& jpgStr)
{
    std::fstream fs;
    fs.open (fileName.c_str(), std::fstream::in);
    if(fs)
    {
        fs.seekg (0, fs.end);
        size_t buffLen = fs.tellg();
        fs.seekg (0, fs.beg);

        char* buff = new char [buffLen];
        fs.read (buff, buffLen);

        if (fs)
            std::cout << "all characters read successfully" << std::endl;
        else
            std::cout << "error: only %d could be read" << std::endl;

        hce::ai::inference::base64EncodeBufferToString(jpgStr, buff, buffLen);

        delete[] buff;
    }

    fs.close();
}

void getAllFiles(std::string path, std::vector<std::string>& imagesVector)
{
    DIR *pDir;
    struct dirent* ptr;
    if(!(pDir = opendir(path.c_str())))
        return;
    while((ptr = readdir(pDir))!=0)
    {
        if (strcmp(ptr->d_name, ".") != 0 && strcmp(ptr->d_name, "..") != 0)
        {
          if (CheckPostFix(ptr->d_name) == true)
          {
              std::string fileName = path + "/" + ptr->d_name;
              std::string imageContent;
              readJpgToCharBuffer(fileName, imageContent);
              imagesVector.push_back(imageContent);
          }
        }   
    }
    closedir(pDir);
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
                "Usage: testQueryPipeline <host> <port> <json_file> <thread_number> <repeats> <image_folder>\n" <<
                "Example:\n" <<
                "    testQueryPipeline www.example.com 80 ./LLPipeline.json 1 10 /path/to/image_folder \n";
            return EXIT_FAILURE;
        }
        std::string host(argv[1]);
        std::string port(argv[2]);
        int version = 11;
        std::string jsonFile(argv[3]);
        unsigned threadNum = atoi(argv[4]);
        unsigned repeats = atoi(argv[5]);
        std::string imageFolder(argv[6]);

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
        getAllFiles(imageFolder, imagesVector);

        std::vector<std::thread> vThs;

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
        float mean = total/g_total.size();
        std::cout<<"Mean time: "<< mean<< " ms"<<std::endl;

        float qps = ((float)threadNum*repeats)/(mean/1000.0);
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
/**
 * example for expected logs:
   [DEBUG] [229] [1637917444262]: LLOutputNode.cpp:124 process Emit: {
    "status_code": "0",
    "description": "succeeded",
    "roi_info": [
        {
            "roi": [
                "1638",
                "0",
                "1077",
                "989"
            ],
            "feature_vector": "CfYY7+oTy\/ooB\/Pn9goP\/w4E8uApEvEF+QLwABMD+PoBEAz3Ah4C8v3++PQHxuLw4QsGBvr1CubzB9v+EQMP5\/jn9gMMCAod\/vwkCAcKD\/Ts8Sor+AwKDSYI1wb9\/xsI8g3j9gYD\/vbY6g4O798o9uvu9uTi+wTsDSn2EeEJ4v\/9+QnoEgD7D\/YQ8vUOBPskDgTy9hgGAg7jDAbp1Q4B+PEF\/Af9CwYIEfoTJ9QY+t\/n+f4F8hLyEen86PwA8uIX9gX\/EQv8GQ\/+BxYO7QIF3AntFAYJ8wn8CQMR\/QLp0+cJ9PUJAe\/rDhYJF9w87usF9x7zDPHwBN\/+8ysE+vEC7v\/55w8O8uPx\/PD+9hf8\/+sF2uX7+w8q9ggd7gb3B\/MA6yACBQXuDvMHCg8R9hET9wL1GfvyBvMD6CAHEOknCwkc6PEG+xQHI\/L\/GfABCe4N7wTv7hbqJf4K+Q0NBvcBCQX6+PUACBYDIjT+H+vr9Q4DCwv\/CQD4\/Qgj7ecBHBLp+wz48gr8AgYB6fYPBR759\/38DArtEOzy9gDp+fcIAgMR6\/H47BMF0CorChkF9ucFCwIDCt4MAfYBA\/bqBBoZ7g31FBYQ\/Af2+AfyAA3aG+4cA\/\/2DukkF\/0v\/wju5gP+IP\/2AAn8\/PzyA\/QN+AMR89oiDQPf7xkH9RX8BwXtAik=",
            "roi_class": "vehicle",
            "roi_score": "0.99999761581420898",
            "track_id": "0",
            "track_status": "0",
            "attribute": {
                "color": "white",
                "color_score": "0.999684215",
                "type": "truck",
                "type_score": "0.995895743"
            },
            "license_plate": "<Sichuan>A6T268"
        }
    ]
  }
 on frame id 0
 ...

 MAKE SURE HTTP/1.1 200 is sent after all images processed done.
    [2021-12-03 01:58:42.065] [DualSinks] [trace] [HTTP]: checking a conn with addr 0x7fd704000f00
    [2021-12-03 01:58:42.065] [DualSinks] [trace] [HTTP]: Adding a reply message with code 200 to reply queue
    [2021-12-03 01:58:42.065] [DualSinks] [trace] [HTTP]: checking a conn with addr 0x7fd704000f00
    [2021-12-03 01:58:42.065] [DualSinks] [trace] [HTTP]: make an http reply
    [2021-12-03 01:58:42.065] [DualSinks] [trace] [HTTP]: http reply string as following: HTTP/1.1 200 OK


 */
//]
