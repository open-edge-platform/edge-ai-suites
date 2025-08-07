// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation

#include "config.h"
#include "ServerSystem.h"

#include <rclcpp/rclcpp.hpp>
#include <spdlog/spdlog.h>

#include <chrono>
#include <memory>
#include <signal.h>

const std::string default_node_name("univloc_server");
bool is_server_node;
class SLAMNode:public rclcpp::Node
{
public:
    SLAMNode();
    ~SLAMNode();

    void init();

    void stop();

private:
    std::unique_ptr<openvslam::ServerSystem> slam_;
    std::shared_ptr<openvslam::config> cfg_;
};



int main(int argc, char** argv)
{
    is_server_node = true;
    std::shared_ptr<SLAMNode> node;
    rclcpp::init(argc, argv);

    node = std::make_shared<SLAMNode>();
    node->init();
    rclcpp::spin(node);
    rclcpp::shutdown();
    node->stop();
    node.reset();
    return 0;
}

SLAMNode::SLAMNode(): rclcpp::Node(default_node_name)
{}

SLAMNode::~SLAMNode() {
    spdlog::debug("DESTRUCT: SLAMNode"); 
    // I tried to do stop() in deconstructor but it is never called even if I do node.reset()
    //stop();
}

void SLAMNode::init()
{
    // load configuration
    cfg_ = std::make_shared<openvslam::config>(this, std::string(CONFIG_PATH));
    // Create SLAM system. It initializes all system threads and gets ready to
    slam_ = std::make_unique<openvslam::ServerSystem>(cfg_, this);
    slam_->startup(true);
}

void SLAMNode::stop()
{
    slam_->shutdown();
}
