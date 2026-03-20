#! /usr/bin/python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Req: ASREQ-1090 ADBSCAN Parameter File
# Jira ID: SL6-2451
#
# The TC verifies the following:
# Start adbscan container
# Setup environment and then start ADBSCAN node
# Check that the algorithm complains that it cannot find topic
# Start again the ADBSCAN node. This time the algorithm should run with success.
# python3 -m atf.atf test --test amr_tests/tests/container/param_parse \
# --location $(pwd)/atf/tests
# pylint: disable=R0801

from atf.tests.amr_tests.tests.util.base_test import AMRTest


class AtfTest(AMRTest):

    def setup(self: AMRTest):

        # this should always be here
        super().setup()

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
            self.testing_targets[0], self.testing_targets[0].term1, env_display=":10.0"
        )
        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term2, env_display=":10.0"
        )
        self.open_container_terminal(self.testing_targets[0], self.testing_targets[0].term3)
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
            sleep=10,
        )

        self.testing_targets[0].run_cmd(
            "cp /opt/ros/${ROS_DISTRO}/share/adbscan_ros2/config/adbscan_sub_2D.yaml "
            "/tmp/adbscan_sub_2D.yaml",
            self.testing_targets[0].term2,
            check_code=True,
        )
        self.testing_targets[0].run_cmd(
            """sed -i "s/Lidar_topic:.*/Lidar_topic: abcd/" /opt/ros/${ROS_DISTRO}/share/adbscan_ros2/config/adbscan_sub_2D.yaml""",  # noqa: E501
            self.testing_targets[0].term2,
            check_code=True,
        )
        self.testing_targets[0].run_cmd(
            """sed -i "s/Lidar_type:.*/Lidar_type: abcd/" /opt/ros/${ROS_DISTRO}/share/adbscan_ros2/config/adbscan_sub_2D.yaml""",  # noqa: E501
            self.testing_targets[0].term2,
            check_code=True,
        )
        log_file_broken_config = "/tmp/adbscan_log1.txt"

        self.testing_targets[0].run_cmd(
            "ros2 run adbscan_ros2 adbscan_sub --ros-args --params-file "
            "/opt/ros/${ROS_DISTRO}/share/adbscan_ros2/config/adbscan_sub_2D.yaml 2>&1 | tee %s"
            % log_file_broken_config,
            self.testing_targets[0].term2,
            check_code=False,
            sleep=15,
        )

        output_check = "topic not found"
        self.testing_targets[0].run_cmd(
            "cat %s|grep '%s'" % (log_file_broken_config, output_check),
            self.testing_targets[0].term3,
        )

        log_file_working = "/tmp/adbscan_log2.txt"
        self.testing_targets[0].run_cmd(
            "ros2 run adbscan_ros2 adbscan_sub --ros-args --params-file "
            "/tmp/adbscan_sub_2D.yaml 2>&1 | tee %s &" % log_file_working,
            self.testing_targets[0].term3,
            check_code=False,
            sleep=10,
        )

        self.testing_targets[0].run_cmd(
            "cat %s|grep -v '%s'" % (log_file_working, output_check), self.testing_targets[0].term3
        )

        return True

    def cleanup(self, success):
        res = super().cleanup(success)
        return res
