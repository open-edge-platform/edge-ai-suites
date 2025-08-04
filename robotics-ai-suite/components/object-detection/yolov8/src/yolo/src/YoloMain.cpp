// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.

#include <iostream>
#include <string>
#include <csignal>
#include <atomic>

#include "CLI11.hpp"
#include "Pipeline.hpp"
#include "Constants.hpp"
#include "PythonDownload.hpp"
#include "toml.hpp"

using namespace std;

string example = R"(
title = "Yolo Ros Node"

[main]
pipelines = ["pipeline1"] # names will be used to name output topics
models = ["model1"]

[model1]
model_path = "" # if empty, model will be downloaded from ultralytics, otherwise provide path to .xml file or other format supported by OpenVINO
model_path_bin = "" # use only if you want to provide your own model in OpenVINO format, and there you need to provide path to .bin file
# following options are only used if model_path is empty
task = "segmentation" # options: detection, segmentation, pose
# w,h of internal resolution, input frames are resized
# consider using smaller resolution for faster inference
width = 640 
height = 480
model_size = "n" # options: n, s, m, l, x (refer to ultralytics docs)
half = true # use half precision


[pipeline1]
model = "model1" # model name from [main] section
device = "CPU"  # options CPU, GPU (this is directly passed to OpenVINO)
performance_mode = 1 # Performance mode 1=Latency, 2=Throughput, 3=Cumulative throughput
priority = 1 # 0=Low, 1=Normal, 2=High
precision = 1 #  0 = FP32, 1 = FP16 , this is passed as hint to OpenVINO
num_requests = 1 # Number of inference requests (hint for OpenVINO) recommended 1 per input stream
map_frame = "map" # setting is ignored if single topic is used, otherwise it will be used to synchronize camera location
queue_size = 10
workers = 2 # Aim for 2 workers per input stream
max_fps = -1 # -1 for unlimited
publish_video = true # publish video with detections
publish_detections = true # publish detections (special message type), can be used to generate video with detections
# use this if you don't have or don't need synchronized depth data
rgb_topic = []
rgb_topic_max_fps = [] # same length as rgb_topic, -1 for unlimited will assume -1 for all topics if not provided
# depth is not used by yolo, but if provided this node will synchronize rgb and depth and transform to camera frame
# this can be later used to place detections in 3D sSpace
# topics need to be provided in pairs
rgbd_topic_rgb = ["/camera/color/image_raw"]
rgbd_topic_depth = ["/camera/depth/image_raw"]
rgbd_topic_max_fps = []
)";

std::atomic<bool> quit(false);  // signal flag

void got_signal(int)
{
    quit.store(true);
}

int main(int argc, char **argv)
{
    try {
        ov::Core core;
        std::signal(SIGINT, got_signal);
        CLI::App app{"YoloV8 Ros Node"};
        std::string toml_path = "pipeline.toml";
        app.add_option("--toml", toml_path, "Path to toml file with configuration");

        CLI11_PARSE(app, argc, argv);
        toml::table config;

        try {
            config = toml::parse_file(toml_path);
        } catch (const toml::parse_error& err) {
            std::cerr << "Parsing failed\n" << err << std::endl;
            std::cout << "Example toml file:" << std::endl;
            std::cout << example << std::endl;
            return 1;
        }

        std::cout << config["title"] << std::endl;
        std::map<std::string, std::pair<std::string, std::string>> models;
        auto *model_names = config["main"]["models"].as_array();
        if (model_names == nullptr) {
            throw std::runtime_error("Models array is missing in the configuration.");
        }

        model_names->for_each([&](auto&& model_name_element) {
            std::string model_name(model_name_element.value_or(""sv));
            std::cout << "Parsing model " << model_name << std::endl;
            std::string model_path(config[model_name]["model_path"].as_string()->value_or(""sv));
            std::string model_path_bin(config[model_name]["model_path_bin"].as_string()->value_or(""sv));

            if (model_path != ""){
                models[model_name] = {model_path,model_path_bin};
                return;
            }

            std::optional<int64_t> width = config[model_name]["width"].value<int64_t>();
            std::optional<int64_t> height = config[model_name]["height"].value<int64_t>();
            std::string task(config[model_name]["task"].value_or<std::string_view>(""sv));
            std::string model_size(config[model_name]["model_size"].value_or<std::string_view>(""sv));
            bool half = config[model_name]["half"].as_boolean()->value_or(true);

            if(!width.has_value()) {
                std::cout << "\033[1;31m" << "Width is empty, please provide width" << "\033[0m" << std::endl;
                raise(SIGINT);
            }
            if(!height.has_value()) {
                std::cout << "\033[1;31m" << "Height is empty, please provide height" << "\033[0m" << std::endl;
                raise(SIGINT);
            }

            if(task =="") {
                std::cout << "\033[1;31m" << "Task is empty, please provide one of the following: detection, segmentation, pose" << "\033[0m" << std::endl;
                raise(SIGINT);
            }
            if(model_size =="") {
                std::cout << "\033[1;31m" << "Model size is empty, please provide one of the following: n, s, m, l, xl" << "\033[0m" << std::endl;
                raise(SIGINT);
            }

            Task task_enum;
            ModelSize model_size_enum;
            try {
                task_enum = task_map.at(task);
                model_size_enum = model_size_map.at(model_size);
            } catch (const std::out_of_range& e) {
                std::cout << "\033[1;31m" << "Invalid model size: " << "\033[0m" << std::endl;
                raise(SIGINT);
            }
            model_path = download_model(cv::Size(width.value(),height.value()),task_enum,half,model_size_enum);
            models[model_name] = {model_path,""};

        });

        std::map<std::string,std::shared_ptr<Pipeline>> pipelines;
        auto *pipeline_names = config["main"]["pipelines"].as_array();
        if (pipeline_names == nullptr) {
            throw std::runtime_error("Pipelines array is missing in the configuration.");
        }

        pipeline_names->for_each([&](auto&& pipeline_name_element) {
            std::string pipeline_name(pipeline_name_element.value_or(""sv));
            std::cout << "Parsing pipeline " << pipeline_name << std::endl;

            std::string model_name(config[pipeline_name]["model"].as_string()->value_or(""sv));
            if(models.find(model_name) == models.end()){
                std::cout << "\033[1;31m" << "Model " << model_name << " not found" << "\033[0m" << std::endl;
                raise(SIGINT);
            }
            std::string device(config[pipeline_name]["device"].as_string()->value_or(""sv));
            if (device == ""){
                device = "CPU";
                std::cout << "\033[1;33m" << "Device is empty, using CPU" << "\033[0m" << std::endl;
            }

            int64_t performance_mode = config[pipeline_name]["performance_mode"].value<int64_t>().value_or(1);
            int64_t priority = config[pipeline_name]["priority"].value<int64_t>().value_or(1);
            int64_t precision = config[pipeline_name]["precision"].value<int64_t>().value_or(1);

            ov::hint::PerformanceMode performance_mode_enum;
            ov::hint::Priority priority_enum;
            ov::hint::ExecutionMode precision_enum;
            try {
                performance_mode_enum = performance_mode_map.at(performance_mode);
                priority_enum = priority_map.at(priority);
                precision_enum = precision_map.at(precision);
            } catch (const std::out_of_range& e) {
                std::cerr << "Invalid performance mode, priority, or precision: " << e.what() << std::endl;
                raise(SIGINT);
            }

            int64_t num_requests = config[pipeline_name]["num_requests"].value<int64_t>().value_or(-1);
            if (num_requests == -1){
                num_requests = 1;
                std::cout << "\033[1;33m" << "Number of requests is empty, using 1" << "\033[0m" << std::endl;
            }

            std::string map_frame(config[pipeline_name]["map_frame"].as_string()->value_or(""sv));
            int64_t queue_size = config[pipeline_name]["queue_size"].value<int64_t>().value_or(10);
            int64_t workers = config[pipeline_name]["workers"].value<int64_t>().value_or(2);
            int64_t max_fps = config[pipeline_name]["max_fps"].value<int64_t>().value_or(-1);
            bool publish_video = config[pipeline_name]["publish_video"].as_boolean()->value_or(true);
            bool publish_detections = config[pipeline_name]["publish_detections"].as_boolean()->value_or(true);

            auto *rgb_topic = config[pipeline_name]["rgb_topic"].as_array();
            auto *rgb_topic_max_fps = config[pipeline_name]["rgb_topic_max_fps"].as_array();
            auto *rgbd_topic_rgb = config[pipeline_name]["rgbd_topic_rgb"].as_array();
            auto *rgbd_topic_depth = config[pipeline_name]["rgbd_topic_depth"].as_array();
            auto *rgbd_topic_max_fps = config[pipeline_name]["rgbd_topic_max_fps"].as_array();

            std::vector<std::string> rgb_topic_vector;
            std::vector<int64_t> rgb_topic_max_fps_vector;

            std::vector<std::string> rgbd_topic_rgb_vector;
            std::vector<std::string> rgbd_topic_depth_vector;
            std::vector<int64_t> rgbd_topic_max_fps_vector;

            if(rgb_topic != nullptr) {
                rgb_topic->for_each([&](auto&& rgb_topic_element) {
                    std::string rgb_topic_string(rgb_topic_element.value_or(""sv));
                    rgb_topic_vector.push_back(rgb_topic_string);
                });
            }

            if(rgb_topic_max_fps != nullptr) {
                rgb_topic_max_fps->for_each([&](auto&& rgb_topic_max_fps_element) {
                    int64_t rgb_topic_max_fps_int(rgb_topic_max_fps_element.value_or(-1));
                    rgb_topic_max_fps_vector.push_back(rgb_topic_max_fps_int);
                });
            }

            if(rgbd_topic_rgb != nullptr) {
                rgbd_topic_rgb->for_each([&](auto&& rgbd_topic_rgb_element) {
                    std::string rgbd_topic_rgb_string(rgbd_topic_rgb_element.value_or(""sv));
                    rgbd_topic_rgb_vector.push_back(rgbd_topic_rgb_string);
                });
            }

            if(rgbd_topic_depth != nullptr){
                rgbd_topic_depth->for_each([&](auto&& rgbd_topic_depth_element) {
                    std::string rgbd_topic_depth_string(rgbd_topic_depth_element.value_or(""sv));
                    rgbd_topic_depth_vector.push_back(rgbd_topic_depth_string);
                });
            }

            if(rgbd_topic_max_fps != nullptr){
                rgbd_topic_max_fps->for_each([&](auto&& rgbd_topic_max_fps_element) {
                    int64_t rgbd_topic_max_fps_int(rgbd_topic_max_fps_element.value_or(-1));
                    rgbd_topic_max_fps_vector.push_back(rgbd_topic_max_fps_int);
                });
            }

            if(rgb_topic_max_fps_vector.size() == 0){
                for (size_t i = 0; i < rgb_topic_vector.size(); i++){
                    rgb_topic_max_fps_vector.push_back(-1);
                }
            }

            if(rgbd_topic_max_fps_vector.size() == 0){
                for (size_t i = 0; i < rgbd_topic_rgb_vector.size(); i++){
                    rgbd_topic_max_fps_vector.push_back(-1);
                }
            }

            if(rgb_topic_max_fps_vector.size() != rgb_topic_vector.size()){
                std::cout << "\033[1;31m" << "rgb_topic and rgb_topic_max_fps need to be same length" << "\033[0m" << std::endl;
                raise(SIGINT);
            }

            if(rgbd_topic_max_fps_vector.size() != rgbd_topic_rgb_vector.size()){
                std::cout << "\033[1;31m" << "rgbd_topic_rgb and rgbd_topic_max_fps need to be same length" << "\033[0m" << std::endl;
                raise(SIGINT);
            }

            if(rgbd_topic_rgb_vector.size() != rgbd_topic_depth_vector.size()){
                std::cout << "\033[1;31m" << "rgbd_topic_rgb and rgbd_topic_depth need to be same length" << "\033[0m" << std::endl;
                raise(SIGINT);
            }

            std::cout << "model_name: " << model_name << std::endl;
            std::cout << "device: " << device << std::endl;
            std::cout << "performance_mode: " << performance_mode << std::endl;
            std::cout << "priority: " << priority << std::endl;
            std::cout << "precision: " << precision << std::endl;
            std::cout << "num_requests: " << num_requests << std::endl;
            std::cout << "map_frame: " << map_frame << std::endl;
            std::cout << "queue_size: " << queue_size << std::endl;
            std::cout << "workers: " << workers << std::endl;
            std::cout << "max_fps: " << max_fps << std::endl;

            for (auto &i : rgb_topic_vector){
                std::cout << "rgb_topic: " << i << std::endl;
            }
            for (auto &i : rgbd_topic_rgb_vector){
                std::cout << "rgbd_topic_rgb: " << i << std::endl;
            }
            for (auto &i : rgbd_topic_depth_vector){
                std::cout << "rgbd_topic_depth: " << i << std::endl;
            }

            std::shared_ptr<Pipeline> pipeline_ptr = std::make_shared<Pipeline>(core);
            pipelines[pipeline_name] = pipeline_ptr;
            pipeline_ptr->configure(
                pipeline_name,
                models[model_name], 
                device, 
                performance_mode_enum,
                priority_enum,
                precision_enum,
                num_requests,
                workers,
                map_frame,
                queue_size,
                publish_video,
                publish_detections
            );

            for (size_t i = 0; i < rgb_topic_vector.size(); i++){
                pipeline_ptr->add_input_topic(rgb_topic_vector[i],rgb_topic_max_fps_vector[i]);
            }
            for (size_t i = 0; i < rgbd_topic_rgb_vector.size(); i++){
                pipeline_ptr->add_joint_rgb_depth_topics(rgbd_topic_rgb_vector[i],rgbd_topic_depth_vector[i],rgbd_topic_max_fps_vector[i]);
            }

        });

        while(!quit.load())
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }

        #ifdef PLOT
        for (auto &i : pipelines){
            i.second->stats.make_latencies_histogram();
            i.second->stats.make_fps_histograms();
            i.second->stats.make_queue_sizes_histogram();
        }
        #endif

    } catch (const CLI::BadNameString& e) {
        std::cerr << "CLI error: " << e.what() << std::endl;
        return 1;
    } catch (const std::out_of_range& e) {
        std::cerr << "Out of range error: " << e.what() << std::endl;
        return 1;
    } catch (const std::exception& e) {
        std::cerr << "Exception caught: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
