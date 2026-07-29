#! /usr/bin/python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Req: ASREQ-1086 ROS 2 Parameters configuration file
# Jira ID: SL6-2457
#
# The TC verifies the following:
# Start adbscan container
# Setup environment and then start ADBSCAN node
# Run the ADBSCAN algorithm using the new launch file.
# (this launchfile contains the parameters from config_params.txt)
# The algorithm should run with success.
# python3 -m atf.atf test --test amr_tests/tests/container/process_lidar_bag \
# --location $(pwd)/atf/tests
# pylint: disable=R0801

from atf.tests.amr_tests.tests.util.base_test import AMRTest


class AtfTest(AMRTest):

    def setup(self: AMRTest):

        # this should always be here
        super().setup()
        # Creating 2 terminal sessions (SSH connections) to run our commands in
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

        self.testing_targets[0].run_cmd(
            "ros2 bag play --loop /tmp/amr-bagfiles/2d-lidar/bagfile/",
            self.testing_targets[0].term1,
            check_code=False,
            check_output="[rosbag2_storage]: Opened database",
        )
        logs_path = "/tmp/log.txt"

        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term2, env_display=":0.0"
        )
        self.testing_targets[0].run_cmd(
            "ros2 run adbscan_ros2 adbscan_sub --ros-args --params-file "
            "/opt/ros/${ROS_DISTRO}/share/adbscan_ros2/config/adbscan_sub_2D.yaml "
            ">%s &" % logs_path,
            self.testing_targets[0].term2,
            check_code=False,
            sleep=30,
        )

        self.testing_targets[0].run_cmd(
            r"log=%s; cat ${log} ;"
            r"grep 'Lidar Message Received' ${log}" % logs_path,
            self.testing_targets[0].term2,
        )

        return True

    def cleanup(self, success):
        # this is just an example of hot to use this function
        # in case you need to add something here
        # the below super().cleanup() line needs to be here always
        res = super().cleanup(success)
        return res
