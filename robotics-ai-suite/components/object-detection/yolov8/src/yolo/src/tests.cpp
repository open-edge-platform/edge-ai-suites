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

#include <gtest/gtest.h>
#include <thread>
#include "Pipeline.hpp" // Assuming the ThreadSafeQueue class is defined in this header file

TEST(ThreadSafeQueueTest, SingleThreadPushAndPop) {
    ThreadSafeQueue<int> queue;
    queue.push(1);
    ASSERT_EQ(queue.pop(), 1);
}

TEST(ThreadSafeQueueTest, MultiThreadPushAndPop) {
    ThreadSafeQueue<int> queue;
    const int num_elements = 1000; // number of elements to push/pop

    std::thread t1([&]() {
        for (int i = 0; i < num_elements; ++i) {
            queue.push(i);
        }
    });

    std::thread t2([&]() {
        for (int i = 0; i < num_elements; ++i) {
            queue.push(i);
        }
    });

    t1.join();
    t2.join();

    ASSERT_EQ(queue.size(), 2 * num_elements);

    for (int i = 0; i < 2 * num_elements; ++i) {
        int popped_value = queue.pop();
        ASSERT_TRUE(popped_value >= 0 && popped_value < num_elements);
    }
}

TEST(ThreadSafeQueueTest, Empty) {
    ThreadSafeQueue<int> queue;
    ASSERT_TRUE(queue.empty());
    queue.push(1);
    ASSERT_FALSE(queue.empty());
}

TEST(ThreadSafeQueueTest, TryPop) {
    ThreadSafeQueue<int> queue;
    ASSERT_FALSE(queue.try_pop().has_value());
    queue.push(1);
    ASSERT_TRUE(queue.try_pop().has_value());
}

TEST(ThreadSafeQueueTest, Size) {
    ThreadSafeQueue<int> queue;
    ASSERT_EQ(queue.size(), 0);
    queue.push(1);
    ASSERT_EQ(queue.size(), 1);
}

// TEST(ImageSyncTest, CallbackCalledWhenImagesAreSynchronized) {
//     ImageSync sync;
//     bool callbackCalled = false;
//     sync.callback = [&](const sensor_msgs::msg::Image::SharedPtr &,
//                         const sensor_msgs::msg::Image::SharedPtr &) {
//         callbackCalled = true;
//     };

//     auto rgbImage = std::make_shared<sensor_msgs::msg::Image>();
//     rgbImage->header.stamp.sec = 1;
//     rgbImage->header.stamp.nanosec = 0;

//     auto depthImage = std::make_shared<sensor_msgs::msg::Image>();
//     depthImage->header.stamp.sec = 1;
//     depthImage->header.stamp.nanosec = 1e9 * 0.01;  // within the acceptable synchronization error

//     sync.callback_rgb(rgbImage);
//     sync.callback_depth(depthImage);

//     ASSERT_TRUE(callbackCalled);
// }

// TEST(ImageSyncTest, CallbackNotCalledWhenImagesAreNotSynchronized) {
//     ImageSync sync;
//     bool callbackCalled = false;
//     sync.callback = [&](const sensor_msgs::msg::Image::SharedPtr &,
//                         const sensor_msgs::msg::Image::SharedPtr &) {
//         callbackCalled = true;
//     };

//     auto rgbImage = std::make_shared<sensor_msgs::msg::Image>();
//     rgbImage->header.stamp.sec = 1;
//     rgbImage->header.stamp.nanosec = 0;

//     auto depthImage = std::make_shared<sensor_msgs::msg::Image>();
//     depthImage->header.stamp.sec = 20;
//     depthImage->header.stamp.nanosec = 1e9 * 0.02;  // outside the acceptable synchronization error

//     sync.callback_rgb(rgbImage);
//     sync.callback_depth(depthImage);

//     ASSERT_FALSE(callbackCalled);
// }


// full pipeline test

// 1. Start the pipeline
// 2. Start ros2 bag
// 3. Start a node that subscribes to the output topics of the pipeline
// 4. Wait for the node to receive the output topics
// 5. Stop the pipeline
// 6. Stop ros2 bag
// 7. Compare the output topics received by the node with the expected output topics
#include <cstdlib>
#include <thread>
#include <atomic>
#include <csignal>
#include <unistd.h>

using namespace std;

std::atomic<bool> finished_flag(false);

void runYolo() {
    pid_t pid = fork();
    if (pid == 0) {
        // This is the child process. Execute the command.
        execlp("yolo", "yolo", "--toml", "../tests/testConfig.toml", (char*)NULL);
    } else if (pid > 0) {
        // This is the parent process. Wait for 60 seconds or until the kill flag is set.
        for (int i = 0; i < 60 && !finished_flag; i++) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
        // Send a SIGINT signal to the child process.
        kill(pid, SIGINT);
    } else {
        // Fork failed
        std::cout << "fork failed!\n";
    }
}

void runBag() {
    pid_t pid = fork();
    if (pid == 0) {
        // This is the child process. Execute the command.
        execlp("ros2", "ros2", "bag", "play", "-l", "./testBag", (char*)NULL);
    } else if (pid > 0) {
        // This is the parent process. Wait for 60 seconds or until the kill flag is set.
        for (int i = 0; i < 60 && !finished_flag; i++) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
        // Send a SIGINT signal to the child process.
        kill(pid, SIGINT);
    } else {
        // Fork failed
        std::cout << "fork failed!\n";
    }
}

class VideoFrameSubscriber : public rclcpp::Node
{
public:
    VideoFrameSubscriber()
        : Node("video_frame_subscriber")
    {
        video_subscription_ = this->create_subscription<sensor_msgs::msg::Image>(
            "video_topic", 10, std::bind(&VideoFrameSubscriber::video_callback, this, std::placeholders::_1));
        frame_subscription_ = this->create_subscription<yolo_msgs::msg::YoloFrame>(
            "frame_topic", 10, std::bind(&VideoFrameSubscriber::frame_callback, this, std::placeholders::_1));
    }

      // check if size of video_results and frame_results are not empty
    optional<pair<sensor_msgs::msg::Image::SharedPtr,yolo_msgs::msg::YoloFrame::SharedPtr>> check_if_finished() {
        if (video_results_.size() > 0 && frame_results_.size() > 0) {
          return {make_pair(video_results_[0], frame_results_[0])};
        }else{
          return {};
        }
    }

private:



    void video_callback(const sensor_msgs::msg::Image::SharedPtr msg)
    {
        video_results_.push_back(msg);
    }

    void frame_callback(const yolo_msgs::msg::YoloFrame::SharedPtr msg)
    {
        frame_results_.push_back(msg);
    }

    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr video_subscription_;
    rclcpp::Subscription<yolo_msgs::msg::YoloFrame>::SharedPtr frame_subscription_;
    std::vector<sensor_msgs::msg::Image::SharedPtr> video_results_;
    std::vector<yolo_msgs::msg::YoloFrame::SharedPtr> frame_results_;
};

// TEST(PipelineFullTest, FullTest1) {
//     // 1. Start the pipeline (run yolo --toml testConfig.toml)
//     std::thread commandThread(runYolo);
//     // Detach the thread to let it run independently
//     commandThread.detach();

//     // 2. Start ros2 bag
//     std::thread bagThread(runBag);
//     // Detach the thread to let it run independently
//     bagThread.detach();


//     // 3. Start a node that subscribes to the output topics of the pipeline
//     rclcpp::init(0, nullptr);
//     auto node = std::make_shared<VideoFrameSubscriber>();
//     // loop wait 1 second , spin some  k times check if finished
//     int k = 30;
//     int it = 0;
//     pair<sensor_msgs::msg::Image::SharedPtr,yolo_msgs::msg::YoloFrame::SharedPtr> result;
//     while (it < k) {
//         rclcpp::spin_some(node);
//         auto result_opt = node->check_if_finished();
//         if (result_opt.has_value()) {
//             result = result_opt.value();
//             break;
//         }
//     }
//     if (it == k) {
//         std::cout << "Test failed: did not receive output topics from the pipeline\n";
//         finished_flag = true;
//         ASSERT_TRUE(false);
//         return;
//     }

//     // test compleated
//     ASSERT_TRUE(true);

    
// }

vector<shared_ptr<thread>> threads;

template <typename T>
void send_ros2_message(typename T::SharedPtr msg, string topic_name, int times = 1, double delay = 0.1) {
    threads.push_back(make_shared<thread>([&,topic_name]() {
        try{
            rclcpp::init(0, nullptr);
        } catch (const std::exception& e) {
            std::cout << "ros already initalized\n";
        }
        rclcpp::Node::SharedPtr node;
        try{
            node = std::make_shared<rclcpp::Node>("senderNode");
        } catch (const std::exception& e) {
            std::cerr << "N0de failed send, " << e.what() << "\n";
            ASSERT_FALSE(true);
        }
        //auto node = std::make_shared<rclcpp::Node>("sender_node");
        cout << "Topic name: " << topic_name << "\n";
        auto publisher = node->create_publisher<T>(topic_name, 10);
        for (int i = 0; i < times; i++) {
            publisher->publish(*msg);
            // spin
            rclcpp::spin_some(node);
            std::this_thread::sleep_for(std::chrono::milliseconds(int(delay * 1000)));
            if (finished_flag) return;
        }
    }));
}

enum STATUS {
    OK,
    ERR,
    AWAITING
};


map<string, atomic<STATUS>> status_map;

template <typename T>
void expect_ros2_message(std::function<bool(T)> check, std::string topic_name, int expected_messages_amount = 1, double delay = 0.5) {
    status_map[topic_name] = AWAITING;
    threads.push_back(make_shared<thread>([&,topic_name]() {
        // try ros init
        try{
            rclcpp::init(0, nullptr);
        } catch (const std::exception& e) {
            std::cerr << "ros already initialized: " << e.what() << "\n";
        }

        STATUS status = AWAITING;
        // topic name but replace / with _
        // std::stringstream ss;
        // for(char c : topic_name) {
        //     if(std::isalnum(c) || c == '_') ss << c;
        //     else ss << '_';
        // }
        // std::string topic_name_ = ss.str();
        
        vector<STATUS> status_vec;
        // mutex
        std::mutex mtx;
        rclcpp::Node::SharedPtr node;
        try{
            node = std::make_shared<rclcpp::Node>("expectNode");
        } catch (const std::exception& e) {
            std::cerr << "N0de failed except, " << e.what() << "\n";
            ASSERT_FALSE(true);
        }
        
        auto subscription = node->create_subscription<T>(
                topic_name, 10, [&](const typename T::SharedPtr msg) {
                    auto status = check(*msg) ? OK : ERR;
                    mtx.lock();
                    status_vec.push_back(status);
                    mtx.unlock();
                });

        // loop wait 1 second , check if expected_messages_amount messages received check if all OK
        while (!finished_flag)
        {
            mtx.lock();
            if (status_map[topic_name] == AWAITING && status_vec.size() >= expected_messages_amount) {
                bool all_ok = true;
                for (auto s : status_vec) {
                    if (s != OK) {
                        all_ok = false;
                        break;
                    }
                }
                if (all_ok) {
                    status_map[topic_name] = OK;
                } else {
                    status_map[topic_name] = ERR;
                }
                mtx.unlock();
                break;
            }
        }
    }));
}

TEST(PipelineFullTest, FullTestV2) {
    // start main thread in a new thread
    std::thread yolo_thread([]() {
        FILE* pipe = popen("./build/yolo/yolo --toml ./src/yolo/tests/testConfig.toml", "r");
        if (!pipe) {
            std::cout << "Failed to start yolo process\n";
            return;
        }

        while (!finished_flag) {
            // sleep for 1 second
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }

        // When finish is true, send SIGKILL to yolo
        system("pkill -SIGKILL yolo");
        pclose(pipe);
    });
    yolo_thread.detach();

#pragma region ros2_msg
    // using opencv load ./src/yolo/tests/test_couple.jpg
    cv::Mat image;
    try{
        image = cv::imread("./src/yolo/tests/test_couple.jpg");
    } catch (const std::exception& e) {
        std::cout << "When loading image: " << e.what() << "\n";
        std::cout << "image not found" << endl;
        ASSERT_FALSE(true);
    }
    // to rgb
    cv::cvtColor(image, image, cv::COLOR_BGR2RGB);

    // to ros2 msg
    sensor_msgs::msg::Image::SharedPtr msg = shared_ptr<sensor_msgs::msg::Image>(new sensor_msgs::msg::Image());
    msg->header.frame_id = "test_frame";
    msg->height = image.rows;
    msg->width = image.cols;
    msg->encoding = "rgb8";
    msg->is_bigendian = false;
    msg->step = image.cols * 3;
    msg->data.resize(image.cols * image.rows * 3);
    //memcpy(&msg->data[0], image.data, image.cols * image.rows * 3);

    // print in yellow
    cout << "\033[33m" << "test_couple.jpg loaded" << "\033[0m" << "\n";
#pragma endregion
    
    // expect ros2 msg from /yolo/frame_topic
    expect_ros2_message<yolo_msgs::msg::YoloFrame>([&](yolo_msgs::msg::YoloFrame msg) {
            cout << "msg.header.frame_id: " << msg.header.frame_id << "\n";
            return msg.header.frame_id == "test_frame";
        }, "/pipeline1/camera/color/image_raw/yolo_frame",5,1.0);
    

    // send ros2 msg to /camera/color/image_raw
    send_ros2_message<sensor_msgs::msg::Image>(msg, "/camera/color/image_raw",20,0.5);

    


    // This is the parent process. Wait for 60 seconds or until the kill flag is set.
    for (int i = 0; i < 10 && !finished_flag; i++) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    // 
    status_map["/pipeline1/camera/color/image_raw/yolo_frame"] = ERR;

    finished_flag = true;


    ASSERT_TRUE(true);
}