#! /usr/bin/python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

""" Req: ASREQ-794 Collaborative SLAM: Local map update on global map update
    Jira ID: SL6-2100

    The test verifies the following:
    1. Start server
    2. Start tracker 1 and tracker 2 in the same time
    3. Play 2 bags containing a common section
    4. Check on the tracker side that landmarks from the server are received,
    corresponding to the global map.  # noqa: E501
    Test execution example:
    python3 -m atf.atf test --test
    amr_tests/tests/collaborative_slam/local_map_update_on_global_map_update
"""
from atf.tests.amr_tests.tests.util.base_test import AMRTest


class AtfTest(AMRTest):
    """Test class for global map update test."""
    def setup(self: AMRTest):
        """Setup for global map update test."""
        # pylint: disable=R0801
        # this should always be here
        super().setup()

        # Creating 4 terminal sessions (SSH connections) to run our commands in
        self.testing_targets[0].open_terminal(ch_name="term1")
        self.testing_targets[0].open_terminal(ch_name="term2")
        self.testing_targets[0].open_terminal(ch_name="term3")
        self.testing_targets[0].open_terminal(ch_name="term4")
        self.testing_targets[0].open_terminal(ch_name="term5")

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

        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term2, env_display=":10.0"
        )
        reference_conf_local_path = self.get_reference_artifact_path("config-map.rviz")
        self.testing_targets[0].run_cmd(
            cmd="docker cp %s %s:/tmp/rviz2_tracker.rviz"  # noqa: E501
            % (reference_conf_local_path, self.test_name),
            terminal_id=self.testing_targets[0].term4,
        )
        self.testing_targets[0].run_cmd(
            cmd="cp /tmp/rviz2_tracker.rviz /opt/ros/${ROS_DISTRO}/share/univloc_tracker/config/rviz2_tracker.rviz",  # noqa: E501
            terminal_id=self.testing_targets[0].term2,
        )

        self.testing_targets[0].run_cmd(
            "ros2 launch univloc_tracker tracker.launch.py "
            "camera:=camera1 publish_tf:=false queue_size:=0 ID:=2 "
            "rviz:=false gui:=false use_odom:=false "
            "vocabulary:=/opt/ros/${ROS_DISTRO}/share/univloc_tracker/config/orb_vocab.dbow2 "
            "log_level:=trace > /tmp/log-tracker1.txt &",
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
            r" grep '\[univloc_tracker_2\]\: Waiting for camera info from camera1/color/camera_info'",  # noqa: E501
            self.testing_targets[0].term2,
        )

        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term3, env_display=":10.0"
        )
        self.testing_targets[0].run_cmd(
            "ros2 launch univloc_tracker tracker.launch.py "
            "publish_tf:=false queue_size:=0 ID:=0 rviz:=true "
            "gui:=false use_odom:=false "
            "vocabulary:=/opt/ros/${ROS_DISTRO}/share/univloc_tracker/config/orb_vocab.dbow2 "
            "log_level:=trace > /tmp/log-tracker2.txt &",
            terminal_id=self.testing_targets[0].term3,
            sleep=10,
            check_code=True,
        )
        self.testing_targets[0].run_cmd(
            "cat /tmp/log-tracker2.txt |"
            r" grep '\[INFO\] \[univloc_tracker_ros-1\]\: process started with pid'",
            self.testing_targets[0].term3,
        )
        self.testing_targets[0].run_cmd(
            "cat /tmp/log-tracker2.txt |"
            r" grep '\[univloc_tracker_0\]\: Waiting for camera info from camera/color/camera_info'",  # noqa: E501
            self.testing_targets[0].term3,
        )

        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term4, env_display=":10.0"
        )
        self.testing_targets[0].run_cmd(
            "ros2 topic hz /univloc_tracker_0/local_map > /tmp/log_pose1.txt &",
            terminal_id=self.testing_targets[0].term4,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            "ros2 bag play /tmp/amr-bagfiles/robot1/bagfile/ "
            "--topics /camera/aligned_depth_to_color/camera_info "
            "/camera/aligned_depth_to_color/image_raw "
            "/camera/color/camera_info /camera/color/image_raw",
            terminal_id=self.testing_targets[0].term4,
            sleep=120,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            r"\[ $(cat /tmp/log_pose1.txt | grep rate | tail -n 1 |"
            r" awk '{print int($3)}') -ge 4 \] && echo 'SUCCESS' || echo 'FAIL'",
            terminal_id=self.testing_targets[0].term4,
            check_output="SUCCESS",
        )

        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term5, env_display=":10.0"
        )
        self.testing_targets[0].run_cmd(
            "ros2 topic hz /univloc_tracker_2/local_map > /tmp/log_pose2.txt &",
            terminal_id=self.testing_targets[0].term5,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            "ros2 bag play /tmp/amr-bagfiles/robot2/bagfile/ "
            "--remap /camera/aligned_depth_to_color/camera_info:=/camera1/aligned_depth_to_color/camera_info "  # noqa: E501
            "/camera/aligned_depth_to_color/image_raw:=/camera1/aligned_depth_to_color/image_raw "
            "/camera/color/camera_info:=/camera1/color/camera_info "
            "/camera/color/image_raw:=/camera1/color/image_raw "
            "--topics /camera/aligned_depth_to_color/camera_info "
            "/camera/aligned_depth_to_color/image_raw "
            "/camera/color/camera_info /camera/color/image_raw",
            terminal_id=self.testing_targets[0].term5,
            sleep=120,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            r"\[ $(cat /tmp/log_pose2.txt | grep rate | tail -n 1 |"
            r" awk '{print int($3)}') -ge 4 \] && echo 'SUCCESS' || echo 'FAIL'",
            terminal_id=self.testing_targets[0].term5,
            check_output="SUCCESS",
        )

        self.testing_targets[0].run_cmd(
            'cat /tmp/log-tracker1.txt | grep "This message is for adding visible server map!"',
            self.testing_targets[0].term5,
        )
        self.testing_targets[0].run_cmd(
            'cat /tmp/log-tracker2.txt | grep "This message is for adding visible server map!"',
            self.testing_targets[0].term5,
        )

        return True

    def cleanup(self, success):
        """Cleanup after global map update test."""
        res = super().cleanup(success)
        return res
