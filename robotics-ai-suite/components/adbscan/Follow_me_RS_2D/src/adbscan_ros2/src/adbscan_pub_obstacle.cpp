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

#include <string>
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "nav2_dynamic_msgs/msg/obstacle.hpp"
#include "nav2_dynamic_msgs/msg/obstacle_array.hpp"

using namespace std::chrono_literals;

class MinimalPublisher : public rclcpp::Node
{
  public:
    MinimalPublisher()
    : Node("adbscan_pub_node")
    {
      publisher_ = this->create_publisher<nav2_dynamic_msgs::msg::Obstacle>("Obstacle_Array", 10);
      timer_ = this->create_wall_timer( 1000ms, std::bind(&MinimalPublisher::publish_message, this));
    }

  private:
    void publish_message()
    {
      auto message = nav2_dynamic_msgs::msg::Obstacle();
      message.position.x = 1.1;
      message.position.y = 1.2;
      message.position.z = 1.3;
      message.size.x = 2.1;
      message.size.y = 2.1;
      message.size.z = 2.1;
      
      RCLCPP_INFO(this->get_logger(), "Publishing: '%f'", (message.size.z));
      publisher_->publish(message);

    }
    rclcpp::TimerBase::SharedPtr timer_;
    rclcpp::Publisher<nav2_dynamic_msgs::msg::Obstacle>::SharedPtr publisher_;
    size_t count_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<MinimalPublisher>());
  rclcpp::shutdown();
  return 0;
}

