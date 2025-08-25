// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "TrackerNode.h"
#include <signal.h>
#include <thread>

std::shared_ptr<TrackerNode> node;

void sigint_handler(int)
{
    rosx::shutdown();
    if (node)
        node->stop();
}

int main(int argc, char **argv)
{
    rosx::init(argc, argv, TrackerNode::tracker_node_name);
    signal(SIGINT, sigint_handler);

    node = std::make_shared<TrackerNode>();
    if (!node->init()) {
        node.reset();
        return EXIT_FAILURE;
    }

    rclcpp::executors::MultiThreadedExecutor executor;
    executor.add_node(node);

    auto trackerThread = std::thread(&TrackerNode::main_loop, node.get());
    executor.spin();
    trackerThread.join();
    node.reset();

    return EXIT_SUCCESS;
}

