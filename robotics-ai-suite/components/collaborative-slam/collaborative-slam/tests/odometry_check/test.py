#! /usr/bin/python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
    Req: ASREQ-1204 Collaborative SLAM: Odometry input
    Jira ID: SL6-2090

    The test verifies the following:
    Launches the server
    Launches the tracker using odom set to false.
    Moves the robot (plays the bag), and observes it loosing tracking
    Stops the Tracker
    Launches the tracker using odom set to true.
    Moves the robot (plays the bag), and observes it no longer loosing tracking

    Test execution example:
    python3 -m atf.atf test --test amr_tests/tests/collaborative_slam/odometry_check

"""
from atf.tests.amr_tests.tests.util.base_test import AMRTest


class AtfTest(AMRTest):
    """Test class for odometry check test."""
    def setup(self: AMRTest):
        """Setup for odometry check test."""
        # pylint: disable=R0801
        # this should always be here
        super().setup()

        # Creating 4 terminal sessions (SSH connections) to run our commands in
        self.testing_targets[0].open_terminal(ch_name="term1")
        self.testing_targets[0].open_terminal(ch_name="term2")
        self.testing_targets[0].open_terminal(ch_name="term3")
        self.testing_targets[0].open_terminal(ch_name="term4")

        # Cleaning up the env on the target
        self.testing_targets[0].run_cmd(
            "pkill Xvfb", self.testing_targets[0].term1, check_code=False
        )
        return True

    def execute(self: AMRTest):
        # pylint: disable=R0801,C0301
        """
        We use Xvfb (implemented by Xorg) because
        it offers a stable, simple xserver in which we can launch
        our programs (Ex: rviz2) and have an easy controllable env (no colors, themes, etc).
        Use disown because when doing a kill we get messages from job control (ex: [1]+ Done).
        """

        self.start_docker_img(
            self.testing_targets[0],
            self.testing_targets[0].term1,
            env_display=":10.0",
            volume_mounts="--volume /tmp/amr-bagfiles:/tmp/amr-bagfiles/ "
            "--volume /tmp/collab-slam/tests/atf/assets:/tmp/assets/collab-slam/ "
            "--volume /tmp/debs:/tmp/debs",
        )
        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term1, env_display=":10.0"
        )
        self.testing_targets[0].run_cmd(
            cmd="Xvfb :10 -ac -screen 0 1680x1050x24 & disown; "
            "sleep 2 ; ps ax | grep Xvfb | grep -v grep",
            terminal_id=self.testing_targets[0].term1,
        )
        self.configure_local_apt_repo(self.testing_targets[0].term1)
        self.testing_targets[0].run_cmd(
            "apt update; apt install /tmp/debs/ros-${ROS_DISTRO}-collab-slam_*.deb -y; "
            "echo finish",
            self.testing_targets[0].term1,
            timeout=300,
            check_output="finish",
        )

        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term2, env_display=":10.0"
        )
        self.testing_targets[0].run_cmd(
            "ros2 launch univloc_server server.launch.py "
            "vocabulary:=/opt/ros/${ROS_DISTRO}/share/univloc_server/config/orb_vocab.dbow2 "
            "gui:=false rviz:=false > /tmp/log-server1.txt &",
            terminal_id=self.testing_targets[0].term1,
            sleep=10,
            check_code=True,
        )

        self.testing_targets[0].run_cmd(
            "cat /tmp/log-server1.txt |"
            r" grep '\[INFO\] \[univloc_server-1\]\: process started with pid'",
            self.testing_targets[0].term1,
        )

        self.testing_targets[0].run_cmd(
            "ros2 launch univloc_tracker tracker.launch.py "
            "publish_tf:=true queue_size:=0 gui:=false rviz:=false "
            "slam_mode:=mapping use_odom:=false "
            "vocabulary:=/opt/ros/${ROS_DISTRO}/share/univloc_tracker/config/orb_vocab.dbow2 >"
            " /tmp/log-tracker1.txt &",
            terminal_id=self.testing_targets[0].term2,
            sleep=10,
            check_code=True,
        )
        self.testing_targets[0].run_cmd(
            "cat /tmp/log-tracker1.txt |"
            r" grep '\[INFO\] \[univloc_tracker_ros-1\]\: process started with pid'",
            self.testing_targets[0].term2,
        )
        self.testing_targets[0].run_cmd(
            "cat /tmp/log-tracker1.txt |"
            r" grep '\[univloc_tracker_0\]\: Waiting for camera info from camera/color/camera_info'",  # noqa: E501
            self.testing_targets[0].term2,
        )

        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term3, env_display=":10.0"
        )

        self.testing_targets[0].run_cmd(
            "ros2 bag play /tmp/amr-bagfiles/NOT-FOR-RELEASE/validation/maze/bagfile/",
            terminal_id=self.testing_targets[0].term3,
            timeout=600,
            sleep=120,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            "pkill -SIGINT univloc_server",
            terminal_id=self.testing_targets[0].term3,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            "pkill -SIGINT univloc_tracker",
            terminal_id=self.testing_targets[0].term3,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            "pkill -SIGINT ros2",
            terminal_id=self.testing_targets[0].term3,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            r"cat /tmp/log-tracker1.txt | grep '\[warning\] tracking lost'",
            self.testing_targets[0].term1,
        )

        self.testing_targets[0].run_cmd(
            "ros2 launch univloc_server server.launch.py "
            "vocabulary:=/opt/ros/${ROS_DISTRO}/share/univloc_server/config/orb_vocab.dbow2 "
            "gui:=false rviz:=false > /tmp/log-server1.txt &",
            terminal_id=self.testing_targets[0].term1,
            sleep=10,
            check_code=True,
        )

        self.testing_targets[0].run_cmd(
            "cat /tmp/log-server1.txt |"
            r" grep '\[INFO\] \[univloc_server-1\]\: process started with pid'",
            self.testing_targets[0].term1,
        )

        self.testing_targets[0].run_cmd(
            "ros2 launch univloc_tracker tracker.launch.py "
            "camera:=camera camera_setup:=RGBD queue_size:=0 "
            "use_odom:=true odom_tf_query_timeout:=50.0 baselink_frame:=base_link "
            "image_frame:=camera_color_optical_frame publish_tf:=false pub_tf_parent_frame:=map "
            "pub_tf_child_frame:=odom rviz:=false gui:=false "
            "log_level:=warning get_camera_extrin_from_tf:=true "
            "vocabulary:=/opt/ros/${ROS_DISTRO}/share/univloc_tracker/config/orb_vocab.dbow2 > "
            "/tmp/log-tracker1.txt &",
            terminal_id=self.testing_targets[0].term2,
            sleep=10,
            check_code=True,
        )
        self.testing_targets[0].run_cmd(
            "cat /tmp/log-tracker1.txt |"
            r" grep '\[INFO\] \[univloc_tracker_ros-1\]\: process started with pid'",
            self.testing_targets[0].term2,
        )
        self.testing_targets[0].run_cmd(
            "cat /tmp/log-tracker1.txt |"
            r" grep '\[univloc_tracker_0\]\: Waiting for camera info from camera/color/camera_info'",  # noqa: E501
            self.testing_targets[0].term2,
        )
        self.testing_targets[0].run_cmd(
            "ros2 bag play /tmp/amr-bagfiles/NOT-FOR-RELEASE/validation/maze/bagfile/",
            terminal_id=self.testing_targets[0].term3,
            timeout=100,
            sleep=60,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            "pkill -SIGINT univloc_server",
            terminal_id=self.testing_targets[0].term3,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            "pkill -SIGINT univloc_tracker",
            terminal_id=self.testing_targets[0].term3,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            "pkill -SIGINT ros2",
            terminal_id=self.testing_targets[0].term3,
            check_code=False,
        )

        self.testing_targets[0].run_cmd(
            r"cat /tmp/log-tracker1.txt | grep -v '\[warning\] tracking lost'",
            self.testing_targets[0].term1,
        )
        return True

    def cleanup(self, success):
        """Cleanup after odometry check test."""
        res = super().cleanup(success)
        return res
