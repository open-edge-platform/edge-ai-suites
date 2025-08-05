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
#include <gtest/gtest.h>

#include <memory>
#include <any>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include <geometry_msgs/msg/pose_stamped.hpp>
#include "univloc_msgs/msg/keyframe.hpp"
#include <visualization_msgs/msg/marker.hpp>
#include <visualization_msgs/msg/marker_array.hpp>

#define TEST_TIMEOUT 150

using namespace std;

class MapMergeTest : public rclcpp::Node
{
public:
    MapMergeTest() : Node("test_map_merge")
    {
        auto qos = rclcpp::QoS {rclcpp::KeepAll()};
        this->markerSubs_ = create_subscription<visualization_msgs::msg::MarkerArray>(
        string("/univloc_server/keyframes"), qos, std::bind(&MapMergeTest::markerCallback, this, std::placeholders::_1));
        this->shouldFail = true;
        this->testStart_ = std::chrono::steady_clock::now();
    }
    ~MapMergeTest() {}

    bool runTest()
    {
        int64_t elapsedSeconds = 0;
        while (elapsedSeconds < TEST_TIMEOUT)
        {
            rclcpp::spin_some(shared_from_this());
            elapsedSeconds = std::chrono::duration_cast<std::chrono::seconds>(std::chrono::steady_clock::now() - this->testStart_).count();
        }
        if (this->shouldFail){
            return false;
        }
        return true;
    }

    void markerCallback(const visualization_msgs::msg::MarkerArray::SharedPtr msg)
    {
        for(const auto& m: msg->markers){
            string ns = m.ns;
            string::size_type idx = ns.find( expectedMarker );
            if(idx != string::npos){
              this->shouldFail = false;
            }
        }
    }

private:
    rclcpp::Subscription<visualization_msgs::msg::MarkerArray>::SharedPtr markerSubs_;
    string expectedMarker = "loop";
    bool shouldFail;
    std::chrono::steady_clock::time_point testStart_;
};

TEST(testMapMerge, testMapMerge)
{
    auto tstMapMerge = make_shared<MapMergeTest>();
    ASSERT_TRUE(tstMapMerge->runTest());
    SUCCEED();
}

int main(int argc, char * argv[])
{
    ::testing::InitGoogleTest(&argc, argv);

    rclcpp::init(argc, argv);

    bool all_successful = RUN_ALL_TESTS();

    rclcpp::shutdown();

    if (all_successful) {
        std::cout << "Didn't detected loop from univloc_server/keyframes topic!" << std::endl;
        exit(1);
    }
    else {
        std::cout << "Detected loop from univloc_server/keyframes topic!" << std::endl;
        exit(0);
    }
}
