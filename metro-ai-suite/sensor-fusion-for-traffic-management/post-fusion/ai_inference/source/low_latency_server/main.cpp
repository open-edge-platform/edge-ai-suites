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

#include <csignal>
#include <cstring>
#include <fstream>
#include <sys/wait.h>
#include <boost/program_options.hpp>
#include <boost/exception/all.hpp>
#include "common/logger.hpp"
#include "low_latency_server/http_server/httpPipelineManager.hpp"
#include "low_latency_server/http_server/lowLatencyServer.hpp"
#include "low_latency_server/grpc_server/grpcPipelineManager.hpp"
#include "low_latency_server/grpc_server/grpcServer.hpp"

using namespace hce::ai::inference;

std::mutex g_mutex;
std::condition_variable g_cv;
std::atomic<bool> g_running;

struct Config{
    std::string logDir;
    unsigned logMaxFileSize;
    unsigned logMaxFileCount;
    unsigned logSeverity;

    std::string httpServerAddr;
    unsigned httpServerPort;
    unsigned gRPCServerPort;

    unsigned numOfProcess;
    unsigned maxConcurrentWorkload;
    unsigned maxPipelineLifetime;
    unsigned pipelineManagerPoolSize;
};

Config parseConf(int argc, char** argv){
    namespace po = boost::program_options;
    std::string confPath;
    po::options_description desc("AI Inference Service options");
    desc.add_options()("help,h", "Print this help message")("config,C", po::value<std::string>(), "path to the configuration file");
    po::variables_map vm;
    po::store(po::parse_command_line(argc, argv, desc), vm);
    po::notify(vm);
    if (vm.count("help")) {
        std::cerr << desc << std::endl;
        exit(EXIT_FAILURE);
    }
    if(vm.count("config")){
	    confPath = vm["config"].as<std::string>();
    }
    else{
        std::cerr << desc << std::endl;
        exit(EXIT_FAILURE);
    }

    Config config;
    try{
        po::options_description confDesc("configuration");
        confDesc.add_options()
            ("Service.logDir", po::value<std::string>(&config.logDir), "path to the log file")
            ("Service.logMaxFileCount", po::value<unsigned>(&config.logMaxFileCount), "max number of log file")
            ("Service.logMaxFileSize", po::value<unsigned>(&config.logMaxFileSize), "max size of log file")
            ("Service.logSeverity", po::value<unsigned>(&config.logSeverity), "log severity")

            ("HTTP.address", po::value<std::string>(&config.httpServerAddr), "HTTP server address")
            ("HTTP.RESTfulPort", po::value<unsigned>(&config.httpServerPort), "HTTP server port")
            ("HTTP.gRPCPort", po::value<unsigned>(&config.gRPCServerPort), "gRPC server port")

            ("Pipeline.numOfProcess", po::value<unsigned>(&config.numOfProcess)->default_value(1), "Number of processes to start. Default as 1.")
            ("Pipeline.maxConcurrentWorkload", po::value<unsigned>(&config.maxConcurrentWorkload), "Max pipeline counts running concurrently")
            ("Pipeline.maxPipelineLifetime", po::value<unsigned>(&config.maxPipelineLifetime)->default_value(30),
                                              "Max pipeline lifetime (seconds). Default as 30.")
            ("Pipeline.pipelineManagerPoolSize", po::value<unsigned>(&config.pipelineManagerPoolSize)->default_value(1),
                                              "Pipeline manager pool size. Default as 1.");

        po::variables_map confVm;
        std::ifstream ifile(confPath, std::ifstream::in);
        if(!ifile.is_open()){
            throw std::invalid_argument("Can not open the config file" );
        }
        po::store(po::parse_config_file(ifile, confDesc), confVm);
        ifile.close();
        po::notify(confVm);

        return config;

    }catch(boost::exception& e){
        std::cerr << "Error parsing config file: " << boost::diagnostic_information(e) << std::endl;
        exit(EXIT_FAILURE);
    }
}

void onExitSignal(int sig, siginfo_t *info, void *ucontext){
    std::cout << "Exiting..." << std::endl;
    g_running.store(false, std::memory_order_release);
    g_cv.notify_all();
}

void startHTTPServer(Config config) {
    HttpPipelineManager::getInstance().init(config.maxConcurrentWorkload, config.maxPipelineLifetime, config.logSeverity);
    HttpPipelineManager::getInstance().start(config.pipelineManagerPoolSize);
    HttpServerLowLatency::getInstance().init(config.httpServerAddr, config.httpServerPort);
    HttpServerLowLatency::getInstance().run();
    if(g_running.load(std::memory_order_acquire)){
        std::unique_lock<std::mutex> lk(g_mutex);
        g_cv.wait(lk, [](){return !g_running.load(std::memory_order_acquire);});
    }
    HttpServerLowLatency::getInstance().stop();
    HttpPipelineManager::getInstance().stop();
}

void startgRPCServer(Config config) {
    GrpcPipelineManager::getInstance().init(config.maxConcurrentWorkload, config.maxPipelineLifetime, config.logSeverity);
    GrpcPipelineManager::getInstance().start(config.pipelineManagerPoolSize);
    GrpcServer::CommConfig commConfig;
    commConfig.serverAddr = config.httpServerAddr + ":" + std::to_string(config.gRPCServerPort);
    commConfig.threadPoolSize = 1;
    GrpcServer::getInstance().init(commConfig);
    GrpcServer::getInstance().start();
    if(g_running.load(std::memory_order_acquire)){
        std::unique_lock<std::mutex> lk(g_mutex);
        g_cv.wait(lk, [](){return !g_running.load(std::memory_order_acquire);});
    }
    GrpcServer::getInstance().stop();
    GrpcPipelineManager::getInstance().stop();
}

int main(int argc, char* argv[]){
    g_running.store(true, std::memory_order_release);

    struct sigaction act;
    memset(&act, 0, sizeof(act));
    act.sa_sigaction = onExitSignal;
    act.sa_flags = SA_SIGINFO;
	sigaction(SIGINT, &act, NULL);

    Config config = parseConf(argc, argv);

    if (config.numOfProcess == 1) {
        Logger::init(config.logDir, config.logMaxFileCount, config.logMaxFileSize, config.logSeverity);

        std::thread t1([config](){startHTTPServer(config);});
        std::thread t2([config](){startgRPCServer(config);});
        t1.join();
        t2.join();

        return 0;
    } else {
        for (int i = 0; i < config.numOfProcess; ++i) {
            pid_t pid = fork();
            if (pid == 0) {
                // Child process
                // 1. Set the pipeline id environment variable
                setenv("PIPELINE_ID", std::to_string(i).c_str(), 1);
                // 2. Dynamically modify gRPC port
                int grpc_port = config.gRPCServerPort + i;
                int restful_port = config.httpServerPort + i;
                // 3. Parse configuration
                Config subConfig = parseConf(argc, argv);
                subConfig.gRPCServerPort = grpc_port;
                subConfig.httpServerPort = restful_port;
                // 4. Log differentiation
                Logger::init(config.logDir + "/pipeline_" + std::to_string(i), subConfig.logMaxFileCount, subConfig.logMaxFileSize, subConfig.logSeverity);

                // 5. Start HTTP/gRPC services (can only start gRPC)
                std::thread t1([subConfig](){startHTTPServer(subConfig);});
                std::thread t2([subConfig](){startgRPCServer(subConfig);});
                t1.join();
                t2.join();
                exit(0);
            }
        }
        // Parent process waits for all child processes
        for (int i = 0; i < config.numOfProcess; ++i) wait(NULL);

        return 0;
    }
}
