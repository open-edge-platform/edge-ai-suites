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
//#include "geometry_msgs/msg/twist.hpp"
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
      //publisher_ = this->create_publisher<std_msgs::msg::String>("laser_scan", 10);
      //publish a nav2 obstacle
     
      publisher_ = this->create_publisher<nav2_dynamic_msgs::msg::ObstacleArray>("Obstacle_Array", 10);
      timer_ = this->create_wall_timer( 1000ms, std::bind(&MinimalPublisher::publish_message, this));
     
    }

  private:
    void publish_message()
    {
      //auto message = std_msgs::msg::String();
      //message.data = "2D coordinate" + std::to_string(count_++);
      RCLCPP_INFO(this->get_logger(), "Ready to publish.");
      auto obstacleArr_msg = nav2_dynamic_msgs::msg::ObstacleArray();
      //std::vector<uint8_t> my_uuid (16, 0);
      nav2_dynamic_msgs::msg::Obstacle tmp_obstacle1;
      for (int i = 0 ; i < 16; i++)
      {
        tmp_obstacle1.uuid.uuid[i] = 0;
      }
      tmp_obstacle1.position.x = 1.1;
      tmp_obstacle1.position.y = 1.2;
      tmp_obstacle1.position.z = 1.3;
      tmp_obstacle1.size.x = 2.1;
      tmp_obstacle1.size.y = 2.2;
      tmp_obstacle1.size.z = 2.3;
      tmp_obstacle1.velocity.x = 0.0;
      tmp_obstacle1.velocity.y = 0.0;
      tmp_obstacle1.velocity.z = 0.0;
      tmp_obstacle1.score = 0.0;


      obstacleArr_msg.obstacles.push_back(tmp_obstacle1);
      nav2_dynamic_msgs::msg::Obstacle tmp_obstacle2;
      for (int i = 0 ; i < 16; i++)
      {
        tmp_obstacle2.uuid.uuid[i] = 1;
      }
      tmp_obstacle2.position.x = 3.1;
      tmp_obstacle2.position.y = 3.2;
      tmp_obstacle2.position.z = 3.3;
      tmp_obstacle2.size.x = 4.1;
      tmp_obstacle2.size.y = 4.2;
      tmp_obstacle2.size.z = 4.3;
      tmp_obstacle2.velocity.x = 0.0;
      tmp_obstacle2.velocity.y = 0.0;
      tmp_obstacle2.velocity.z = 0.0;
      tmp_obstacle2.score = 0.0;

      obstacleArr_msg.obstacles.push_back(tmp_obstacle2);

      //RCLCPP_INFO(this->get_logger(), "Publishing: '%s'", message.data.c_str());

      publisher_->publish(obstacleArr_msg);
      RCLCPP_INFO(this->get_logger(), "Publishing size(): '%d'", (obstacleArr_msg.obstacles).size()); // (message.obstacles[0].size.z));
      RCLCPP_INFO(this->get_logger(), "Publishing size.x: '%f'", obstacleArr_msg.obstacles[1].size.x);

    }
    rclcpp::TimerBase::SharedPtr timer_;
    rclcpp::Publisher<nav2_dynamic_msgs::msg::ObstacleArray>::SharedPtr publisher_;
    //size_t count_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  //rclcpp::spin(std::make_shared<MinimalPublisher>());
  try
  {
    rclcpp::spin(std::make_shared<MinimalPublisher>());
  }
  catch(...)
  {
    std::cerr << "Failed to run adbscan_pub node. " << std::endl;
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::shutdown();
  return 0;
}
