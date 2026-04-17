#! /usr/bin/python3
# Copyright (C) 2022 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# ASREQ-1088 ROS 2 Launch File Parameters
#
#
# Example on how to run this test:
#
# python3 -m atf.atf test --test amr_tests/tests/container/obstacle_array_output_check \
# --location $(pwd)/atf/tests
#
# pylint: disable=R0801

from atf.tests.amr_tests.tests.util.base_test import AMRTest


class AtfTest(AMRTest):

    def setup(self: AMRTest):

        # this should always be here
        super().setup()

        # Creating 3 terminal sessions (SSH connections) to run our commands in
        self.testing_targets[0].open_terminal(ch_name="term1")
        self.testing_targets[0].open_terminal(ch_name="term2")
        self.testing_targets[0].open_terminal(ch_name="term3")

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

        self.testing_targets[0].run_cmd(
            "ros2 bag play --loop /tmp/amr-bagfiles/2d-lidar/bagfile/ ",
            self.testing_targets[0].term1,
            check_code=False,
            check_output="[rosbag2_storage]: Opened database",
        )

        self.open_container_terminal(self.testing_targets[0], self.testing_targets[0].term2)

        self.testing_targets[0].run_cmd(
            "ros2 run adbscan_ros2 adbscan_sub --ros-args --params-file "
            "/opt/ros/${ROS_DISTRO}/share/adbscan_ros2/config/adbscan_sub_2D.yaml",
            self.testing_targets[0].term2,
            check_code=False,
            check_output="[adbscan_sub_node]: Msg: number of input points: '1440'",
        )

        self.open_container_terminal(self.testing_targets[0], self.testing_targets[0].term3)

        self.testing_targets[0].run_cmd(
            "ros2 topic list",
            self.testing_targets[0].term3,
            check_code=False,
            check_output="/obstacle_array",
        )

        self.testing_targets[0].run_cmd(
            "ros2 topic echo /obstacle_array | tee -a /tmp/obstacle_array_log.txt &",
            self.testing_targets[0].term3,
            check_code=False,
            check_output="obstacles:",
            timeout=30,
            sleep=5,
        )

        self.testing_targets[0].run_cmd(
            'no_x_coords=$(cat /tmp/obstacle_array_log.txt | grep "x:" | wc -l); \
                                        echo "Found no_x_coords:${no_x_coords}" && \
                                        test $no_x_coords -gt 3',
            self.testing_targets[0].term3,
        )
        return True

    def cleanup(self, success):
        # after sending to target we can clean the output folder content since we don't
        # needthose files to be uploaded in jira
        return super().cleanup(success)
