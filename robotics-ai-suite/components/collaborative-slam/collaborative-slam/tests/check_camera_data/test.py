#! /usr/bin/python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
    Req: ASREQ-1210 Collaborative SLAM: RGBD sensor input
    Jira ID: SL6-2088

    The test verifies the following:
    1. Launch the tracker and play the rosbag
    2. Open Rviz on tracker side - Add -> camera -> color -> image_raw -> camera
    3. Check in Rviz if the tracker get data from the real camera. Check in rviz
        that the map is displayed  # noqa: E501
    Test execution example:
    python3 -m atf.atf test --test amr_tests/tests/collaborative_slam/check_camera_data
"""
import os
from pathlib import Path

from atf.tests.amr_tests.tests.util.base_test import AMRTest


class AtfTest(AMRTest):
    """Test class for check camera data test."""
    def setup(self: AMRTest):
        """Setup for check camera data test."""
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
        # pylint: disable=R0801,C0301,C0209
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
        self.configure_local_apt_repo(self.testing_targets[0].term1)
        self.testing_targets[0].run_cmd(
            "apt update; apt install /tmp/debs/ros-${ROS_DISTRO}-collab-slam_*.deb -y; "
            "echo finish",
            self.testing_targets[0].term1,
            timeout=300,
            check_output="finish",
        )
        rviz_config_path = self.get_reference_artifact_path("config-map.rviz")
        self.testing_targets[0].run_cmd(
            cmd="docker cp %s %s:/tmp/rviz2_tracker.rviz"
            % (rviz_config_path, self.test_name),
            terminal_id=self.testing_targets[0].term3,
        )

        self.testing_targets[0].run_cmd(
            cmd="cp /tmp/rviz2_tracker.rviz /opt/ros/${ROS_DISTRO}/share/univloc_tracker/config/rviz2_tracker.rviz",  # noqa: E501
            terminal_id=self.testing_targets[0].term1,
        )

        self.testing_targets[0].run_cmd(
            cmd="Xvfb :10 -ac -screen 0 1680x1050x24 & disown; "
            "sleep 2 ; ps ax | grep Xvfb | grep -v grep",
            terminal_id=self.testing_targets[0].term1,
        )

        self.testing_targets[0].run_cmd(
            "ros2 launch univloc_tracker tracker.launch.py "
            "publish_tf:=false queue_size:=0 ID:=0 rviz:=true gui:=false "
            "use_odom:=false slam_mode:=mapping "
            "vocabulary:=/opt/ros/${ROS_DISTRO}/share/univloc_tracker/config/orb_vocab.dbow2 >"
            " /tmp/log-tracker1.txt &",
            terminal_id=self.testing_targets[0].term1,
            sleep=10,
            check_code=True,
        )
        self.testing_targets[0].run_cmd(
            "cat /tmp/log-tracker1.txt |"
            r" grep '\[INFO\] \[univloc_tracker_ros-1\]\: process started with pid'",
            self.testing_targets[0].term1,
        )
        self.testing_targets[0].run_cmd(
            "cat /tmp/log-tracker1.txt |"
            r" grep '\[univloc_tracker_0\]\: Waiting for camera info from camera/color/camera_info'",  # noqa: E501
            self.testing_targets[0].term1,
        )

        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term3, env_display=":10.0"
        )
        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term2, env_display=":10.0"
        )

        self.testing_targets[0].run_cmd(
            "ros2 bag play /tmp/amr-bagfiles/robot2/bagfile "
            "--topics /camera/aligned_depth_to_color/camera_info "
            "/camera/aligned_depth_to_color/image_raw /camera/color/camera_info "
            "/camera/color/image_raw",
            terminal_id=self.testing_targets[0].term3,
            timeout=60,
            check_code=False,
        )

        self.testing_targets[0].run_cmd(
            "ros2 topic hz /univloc_tracker_0/local_map > /tmp/log_map.txt &",
            terminal_id=self.testing_targets[0].term2,
            timeout=10,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            "ros2 topic hz /camera/color/image_raw > /tmp/log_image.txt &",
            terminal_id=self.testing_targets[0].term2,
            timeout=70,
            sleep=60,
            check_code=False,
        )

        self.testing_targets[0].run_cmd(
            "cat /tmp/log_map.txt", terminal_id=self.testing_targets[0].term2
        )
        self.testing_targets[0].run_cmd(
            r"\[ $(cat /tmp/log_map.txt | grep rate | tail -n 1 |"
            r" awk '{print int($3)}') -ge 5 \] && echo 'SUCCESS' || echo 'FAIL'",
            terminal_id=self.testing_targets[0].term2,
            check_output="SUCCESS",
        )

        self.testing_targets[0].run_cmd(
            "cat /tmp/log_image.txt", terminal_id=self.testing_targets[0].term2
        )
        self.testing_targets[0].run_cmd(
            r"\[ $(cat /tmp/log_image.txt | grep rate | tail -n 1 |"
            r" awk '{print int($3)}') -ge 5 \] && echo 'SUCCESS' || echo 'FAIL'",
            terminal_id=self.testing_targets[0].term2,
            check_output="SUCCESS",
        )

        reference_negative_local_path = self.get_reference_artifact_path("map.png")
        screenshot_name = "rviz.png"
        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term4, env_display=":10.0"
        )

        screenshot_remote_path = self.take_screenshot(
            screenshot_name, self.testing_targets[0], self.testing_targets[0].term4
        )
        os.makedirs(Path(self.local_test_output_dir), exist_ok=True)
        self.testing_targets[0].run_cmd(cmd="exit", terminal_id=self.testing_targets[0].term1)
        self.testing_targets[0].run_cmd(
            cmd="docker cp %s:%s %s"
            % (self.test_name, screenshot_remote_path, screenshot_remote_path),
            terminal_id=self.testing_targets[0].term1,
        )
        screenshot_local_full_path = os.path.join(self.local_test_output_dir, screenshot_name)

        self.get_file_from_target(
            screenshot_remote_path, screenshot_local_full_path, self.testing_targets[0]
        )

        return self.is_same_image(
            reference_negative_local_path,
            screenshot_local_full_path,
            10,
            fail_on_size=False,
        )

    def cleanup(self, success):
        """Cleanup for check camera data test."""
        res = super().cleanup(success)
        return res
