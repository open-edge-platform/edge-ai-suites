#! /usr/bin/python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Req: ASREQ-1073 ROS 2
# Req: ASREQ-1076 ROS 2 Foxy
# Req: ASREQ-1079 ROS 2 Topic Publication
# Req: ASREQ-1080 ROS 2 Topic Subscription
# Req: ASREQ-1081 Sensor Message - 2D LiDAR
# Req: ASREQ-1083 Obstacle Array
# Req: ASREQ-1087 ROS 2 Command Line Parameters
# Req: ASREQ-1095 Ubuntu Desktop
# Jira ID: SL6-2359
#
# The TC verifies the following:
# start adbscan docker image and adbscan node with required parameters
# confirm existence of adbscan topic
# python3 -m atf.atf test --test amr_tests/tests/container/obstacle_array_topic_check \
# --location $(pwd)/atf/tests
# pylint: disable=R0801
from atf.tests.amr_tests.tests.util.base_test import AMRTest


class AtfTest(AMRTest):

    def setup(self: AMRTest):

        # this should always be here
        super().setup()

        self.testing_targets[0].open_terminal(ch_name="term1")

        return True

    def execute(self: AMRTest):

        self.start_docker_img(
            self.testing_targets[0],
            self.testing_targets[0].term1,
            env_display=":10.0",
            volume_mounts="--volume /tmp/amr-bagfiles:/tmp/amr-bagfiles/ "
            "--volume /tmp/debs:/tmp/debs",
        )

        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term1, env_display=":10.0"
        )
        self.configure_local_apt_repo(self.testing_targets[0].term1)
        self.testing_targets[0].run_cmd(
            "apt update; apt install -y /tmp/debs/ros-${ROS_DISTRO}-adbscan-ros2_*; echo 'finish'",
            self.testing_targets[0].term1,
            check_code=False,
            timeout=300,
            check_output="finish",
        )

        self.testing_targets[0].run_cmd(
            "ros2 bag play --loop /tmp/amr-bagfiles/2d-lidar/bagfile/ &",
            self.testing_targets[0].term1,
            check_code=False,
            sleep=10,
        )

        self.testing_targets[0].run_cmd(
            "ros2 run adbscan_ros2 adbscan_sub --ros-args -p 'Lidar_type:=2D' "
            "-p 'Lidar_topic:=/scan' -p 'Verbose:=true' -p 'subsample_ratio:=5.0' "
            "-p 'x_filter_back:=4.0' -p 'y_filter_left:=10.0' -p 'y_filter_right:=-20.0' "
            "-p 'z_filter:=-1.3' -p 'Z_based_ground_removal:=1.0' -p 'base:=2.24585885' "
            "-p 'coeff_1:=-0.350137' -p 'coeff_2:=-0.22432557' -p 'scale_factor:=0.1' &",
            self.testing_targets[0].term1,
            check_code=False,
            sleep=20,
        )
        # check topic list
        self.testing_targets[0].run_cmd(
            "ros2 topic list -t",
            self.testing_targets[0].term1,
            check_code=False,
            check_output="nav2_dynamic_msgs/msg/ObstacleArray",
        )

        return True

    def cleanup(self, success):
        res = super().cleanup(success)
        return res
