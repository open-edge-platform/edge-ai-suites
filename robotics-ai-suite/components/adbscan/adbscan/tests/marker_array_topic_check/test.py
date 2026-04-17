#! /usr/bin/python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# ASREQ-1085 Visualization
#
# SL6-2390: [VAL] Automate SL6-2390 in ATF 2.0
# This test verifies that ADBSCAN outputs to a topic
# "marker_array" of type 'visualization_msgs/MarkerArray'.
#
# python3 -m atf.atf test --test amr_tests/tests/container/marker_array_topic_check \
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
            "ros2 bag play --loop /tmp/amr-bagfiles/laser-pointcloud/bagfile &",
            self.testing_targets[0].term1,
            check_code=False,
            sleep=10,
        )

        self.testing_targets[0].run_cmd(
            "ros2 run adbscan_ros2 adbscan_sub --ros-args -p 'Lidar_type:=RS' -p"
            " 'Lidar_topic:=/camera/depth/color/points' -p 'Verbose:=true' -p"
            " 'subsample_ratio:=500.0' -p 'x_filter_back:=4.0' -p 'y_filter_left:=10.0' -p"
            " 'y_filter_right:=-20.0' -p 'z_filter:=-1.3' -p 'Z_based_ground_removal:=1.0'"
            " -p 'base:=3.4694' -p 'coeff_1:=-0.0335' -p 'coeff_2:=0.00015124'"
            " -p 'scale_factor:=0.9' &",
            self.testing_targets[0].term1,
            check_code=False,
            sleep=10,
        )
        # check topic list
        self.testing_targets[0].run_cmd(
            "ros2 topic list -t",
            self.testing_targets[0].term1,
            check_code=False,
            check_output="/marker_array [visualization_msgs/msg/MarkerArray]",
        )

        return True

    def cleanup(self, success):

        res = super().cleanup(success)
        return res
