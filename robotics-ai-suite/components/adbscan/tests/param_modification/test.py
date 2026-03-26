#! /usr/bin/python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Req: ASREQ-1089 Programmatically Setting Parameters of ROS 2 node
# Jira ID: SL6-2453
#
# The TC verifies the following:
# Start adbscan container
# Setup environment and then start ADBSCAN node from adbscan_ros2 folder.
# Get the parameters list
# Change the value for one parameter and check that this value was changed successfully
#
# python3 -m atf.atf test --test amr_tests/tests/container/param_modification \
# --location $(pwd)/atf/tests
# pylint: disable=R0801

from atf.tests.amr_tests.tests.util.base_test import AMRTest


class AtfTest(AMRTest):

    def setup(self: AMRTest):

        # this should always be here
        super().setup()

        self.testing_targets[0].open_terminal(ch_name="term1")
        self.testing_targets[0].open_terminal(ch_name="term2")

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
            self.testing_targets[0], self.testing_targets[0].term1, env_display=":0.0"
        )

        self.configure_local_apt_repo(self.testing_targets[0].term1)
        self.testing_targets[0].run_cmd(
            "apt update; apt install -y /tmp/debs/ros-${ROS_DISTRO}-adbscan-ros2_*; echo 'finish'",
            self.testing_targets[0].term1,
            check_code=False,
            timeout=300,
            check_output="finish",
        )

        log_bag_path = "/tmp/log_bag.txt"
        self.testing_targets[0].run_cmd(
            "ros2 bag play --loop /tmp/amr-bagfiles/2d-lidar/bagfile/ > %s 2>&1 &" % log_bag_path,
            self.testing_targets[0].term1,
            check_code=False,
            sleep=10,
        )

        log_file_without_params = "/tmp/adbscan_log1.txt"
        self.testing_targets[0].run_cmd(
            "ros2 run adbscan_ros2 adbscan_sub --ros-args -p 'Lidar_type:=2D'"
            " -p 'Lidar_topic:=/scan' -p 'Verbose:=true' -p 'subsample_ratio:=5.0'"
            " -p 'x_filter_back:=4.0' -p 'y_filter_left:=10.0' -p 'y_filter_right:=-20.0'"
            " -p 'z_filter:=-1.3' -p 'Z_based_ground_removal:=1.0' -p 'base:=2.24585885'"
            " -p 'coeff_1:=-0.350137' -p 'coeff_2:=-0.22432557' -p 'scale_factor:=0.1' > %s 2>&1 &"
            % log_file_without_params,
            self.testing_targets[0].term1,
            check_code=False,
            sleep=10,
        )

        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term2, env_display=":0.0"
        )

        self.testing_targets[0].run_cmd(
            "ros2 param list",
            self.testing_targets[0].term2,
            check_code=False,
            check_output="/adbscan_sub_node:",
        )

        self.testing_targets[0].run_cmd(
            "ros2 param get adbscan_sub_node Verbose",
            self.testing_targets[0].term2,
            check_code=False,
            check_output="Boolean value is: True",
        )

        self.testing_targets[0].run_cmd(
            "ros2 param set adbscan_sub_node Verbose false",
            self.testing_targets[0].term2,
            check_code=False,
            check_output="Set parameter successful",
        )

        self.testing_targets[0].run_cmd(
            "ros2 param get adbscan_sub_node Verbose",
            self.testing_targets[0].term2,
            check_code=False,
            check_output="Boolean value is: False",
        )

        return True
