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

#include <memory>
#include <string>
#include <atomic>
#include <cmath>

#include <gtest/gtest.h>

#include <rclcpp/rclcpp.hpp>
#include <univloc_msgs/msg/imu_status.hpp>

#define EPSILON    0.00001

int bad_imu_num = 0;
int bad_imu_threshold = 0;
bool imu_robust_init = false;

class TrackerMonitor : public rclcpp::Node
{
public:
    TrackerMonitor()
    : Node("tracker_monitor")
    {
        bad_imu_status_ = ATOMIC_VAR_INIT(0);
        finish_imu_initialization_ = ATOMIC_VAR_INIT(false);

        bad_imu_threshold = declare_parameter<int>("imu_threshold", 0);

        auto qos = rclcpp::SensorDataQoS();
        sub_imu_status_ = this->create_subscription<univloc_msgs::msg::ImuStatus>(
        "univloc_tracker_0/imu_states", qos, std::bind(&TrackerMonitor::imu_status_callback, this,
        std::placeholders::_1));
    }

    int get_bad_imu_num() const
    {
        return bad_imu_status_;
    }

private:
    void imu_status_callback(const univloc_msgs::msg::ImuStatus::SharedPtr msg)
    {
        if (msg->duration < EPSILON) {
            bad_imu_status_++;
            return;
        }

        float modulus_r = sqrt(pow(msg->vec_r[0], 2) + pow(msg->vec_r[1], 2) + pow(msg->vec_r[2], 2));
        float modulus_p = sqrt(pow(msg->vec_p[0], 2) + pow(msg->vec_p[1], 2) + pow(msg->vec_p[2], 2));
        float modulus_v = sqrt(pow(msg->vec_v[0], 2) + pow(msg->vec_v[1], 2) + pow(msg->vec_v[2], 2));
        if (modulus_r < EPSILON || modulus_p < EPSILON || modulus_v < EPSILON) {
            bad_imu_status_++;
            std::cout << "~~~~~~~ bad_imu_status: " <<  bad_imu_status_ << " ~~~~~~~" << std::endl <<
                         "modulus_r: " << modulus_r << " modulus_p: " << modulus_p <<
                         " modulus_v: " << modulus_v << std::endl;
            return;
        }

        // IMU initialization stage
        if (!finish_imu_initialization_) {
            if (msg->initialize_times == 3) {
                finish_imu_initialization_ = true;
                imu_robust_init = true;
            }
        // Finish IMU initialization and fail if IMU resets
        } else {
            if (msg->initialize_times != 3)
                imu_robust_init = false;
        }
    }

    rclcpp::Subscription<univloc_msgs::msg::ImuStatus>::SharedPtr sub_imu_status_;
    std::atomic_int bad_imu_status_;
    std::atomic_bool finish_imu_initialization_;
};

std::shared_ptr<TrackerMonitor> node;

TEST(testImuSystem, testImuSystem)
{
    node = std::make_shared<TrackerMonitor>();
    rclcpp::spin(node);

    node.reset();
    if (!imu_robust_init) {
        std::cout << "Failed to finish IMU initialization or IMU resets after initialization" << std::endl;
        FAIL();
    } else {
        std::cout << "Succeeded to finish IMU initialization and never reset after initialization" << std::endl;
    }

    if (bad_imu_num > bad_imu_threshold) {
        std::cout << "Total bad imu num is: " << bad_imu_num << ", which is larger than threshold: " <<
        bad_imu_threshold << std::endl;
        FAIL();
    } else {
        std::cout << "Total bad imu num is: " << bad_imu_num << ", which is equal or smaller than threshold: " <<
        bad_imu_threshold << std::endl;
    }
    SUCCEED();
}

void sigint_handler(int)
{
    rclcpp::shutdown();
    bad_imu_num = node->get_bad_imu_num();
}

int main(int argc, char * argv[])
{
    ::testing::InitGoogleTest(&argc, argv);

    rclcpp::init(argc, argv);
    signal(SIGINT, sigint_handler);

    bool all_successful = RUN_ALL_TESTS();
    return all_successful;
}
