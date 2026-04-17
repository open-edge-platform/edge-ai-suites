#! /usr/bin/python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
    Req:
    ASREQ-1199 Collaborative SLAM: Landmark request on sensor input
    ASREQ-1201 Collaborative SLAM: Landmark response
    ASREQ-1202 Collaborative SLAM: Pose update on landmark response
    Jira ID: SL6-2120
        The test verifies the following:
    Starts server in mapping mode and specify the save map path
    Starts tracker 1
    Moves the robot (play the rosbag)
    Closes the server and the tracker.
    Checks if the global map was saved in a file.
    Starts the server again but now in localization mode using the
        path from where to load the map
    Checks if server load the global map from the saved file.
        Test execution example:
    python3 -m atf.atf test --test
    amr_tests/tests/collaborative_slam/pose_update_on_global_map_loading
"""
import os

from atf.tests.amr_tests.tests.util.base_test import AMRTest


class AtfTest(AMRTest):
    """Test class for pose update on global map loading test."""
    def setup(self: AMRTest):
        """Setup for pose update on global map loading test."""
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
        self.testing_targets[0].run_cmd(
            cmd="Xvfb :10 -ac -screen 0 1680x1050x24 & disown; "
            "sleep 2 ; ps ax | grep Xvfb | grep -v grep",
            terminal_id=self.testing_targets[0].term1,
        )
        self.configure_local_apt_repo(self.testing_targets[0].term1)
        self.testing_targets[0].run_cmd(
            "apt update; apt install /tmp/debs/ros-${ROS_DISTRO}-collab-slam_*.deb -y;"
            "echo finish",
            self.testing_targets[0].term1,
            timeout=300,
            check_output="finish",
        )
        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term2, env_display=":10.0"
        )
        reference_conf_local_path = self.get_reference_artifact_path("config-map.rviz")
        self.testing_targets[0].run_cmd(
            cmd="docker cp %s %s:/tmp/rviz2_server.rviz"  # noqa: E501
            % (reference_conf_local_path, self.test_name),
            terminal_id=self.testing_targets[0].term4,
        )
        self.testing_targets[0].run_cmd(
            cmd="cp /tmp/rviz2_server.rviz /opt/ros/${ROS_DISTRO}/share/univloc_server/config/rviz2_server.rviz",  # noqa: E501
            terminal_id=self.testing_targets[0].term2,
        )

        percentage_local_path = self.get_reference_artifact_path("check_percentage.sh")
        self.testing_targets[0].run_cmd(
            cmd="docker cp %s %s:/tmp/check_percentage.sh"
            % (percentage_local_path, self.test_name),
            terminal_id=self.testing_targets[0].term4,
        )

        self.testing_targets[0].run_cmd(
            "ros2 launch univloc_server server.launch.py fix_scale:=true"
            " save_map_path:=/tmp/map_maze_bag.msg"
            " save_traj_folder:=/tmp/traj"
            " gui:=false rviz:=true >"
            " /tmp/log-server1.txt &",
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
            "publish_tf:=false queue_size:=0 ID:=0 rviz:=false "
            "gui:=false use_odom:=false > "
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
            "ros2 bag play /tmp/amr-bagfiles/robot2/bagfile/ "
            "--topics /camera/aligned_depth_to_color/camera_info "
            "/camera/aligned_depth_to_color/image_raw "
            "/camera/color/camera_info /camera/color/image_raw",
            terminal_id=self.testing_targets[0].term3,
            sleep=120,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            "pkill -f -SIGINT univloc_server",
            terminal_id=self.testing_targets[0].term3,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            "pkill -f -SIGINT univloc_tracker",
            terminal_id=self.testing_targets[0].term3,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            "pkill -f -SIGINT ros2",
            terminal_id=self.testing_targets[0].term3,
            check_code=False,
        )

        self.testing_targets[0].run_cmd("ls -lah /tmp/map_maze_bag.msg",
                                        self.testing_targets[0].term3)
        self.testing_targets[0].run_cmd("ls -lah /tmp/traj", self.testing_targets[0].term3)

        self.testing_targets[0].run_cmd(
            "ros2 launch univloc_server server.launch.py "
            "fix_scale:=true server_mode:=localization "
            "load_map_path:=/tmp/map_maze_bag.msg log_level:=trace gui:=false rviz:=true >"
            " /tmp/log-server1.txt &",
            terminal_id=self.testing_targets[0].term1,
            sleep=10,
            check_code=True,
        )

        self.testing_targets[0].run_cmd(
            "cat /tmp/log-server1.txt |"
            r" grep '\[INFO\] \[univloc_server-1\]\: process started with pid'",
            self.testing_targets[0].term1,
        )

        reference_local_path = self.get_reference_artifact_path("s2.png")
        screenshot_name = "rviz.png"
        self.open_container_terminal(
            self.testing_targets[0], self.testing_targets[0].term4, env_display=":10.0"
        )
        screenshot_remote_path = self.take_screenshot(
            screenshot_name, self.testing_targets[0], self.testing_targets[0].term4
        )
        screenshot_local_full_path = os.path.join(self.local_test_output_dir, screenshot_name)
        self.testing_targets[0].run_cmd(cmd="exit", terminal_id=self.testing_targets[0].term4)
        self.testing_targets[0].run_cmd(
            cmd="docker cp %s:%s %s"
            % (self.test_name, screenshot_remote_path, screenshot_local_full_path),
            terminal_id=self.testing_targets[0].term4,
        )

        if not self.is_same_image(reference_local_path, screenshot_local_full_path, 2.1, False):
            return False

        self.testing_targets[0].run_cmd(
            "ros2 launch univloc_tracker tracker.launch.py "
            "publish_tf:=true queue_size:=0 ID:=0 rviz:=false gui:=false "
            "slam_mode:=localization traj_store_path:=/tmp/traj/ log_level:=trace >"
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
            "ros2 bag play /tmp/amr-bagfiles/robot2/bagfile/ "
            "--topics /camera/aligned_depth_to_color/camera_info "
            "/camera/aligned_depth_to_color/image_raw /camera/color/camera_info "
            "/camera/color/image_raw ",
            terminal_id=self.testing_targets[0].term3,
            sleep=120,
            check_code=False,
        )
        self.testing_targets[0].run_cmd(
            "cat /tmp/log-tracker1.txt |" + ' grep "Send request of server landmarks for frame"',
            self.testing_targets[0].term2,
        )
        self.testing_targets[0].run_cmd("/tmp/check_percentage.sh", self.testing_targets[0].term2)
        return True

    def cleanup(self, success):
        """Cleanup after pose update on global map loading test."""
        # this is just an example of how to use this function
        # in case you need to add something here
        # the below super().cleanup() line needs to be here always
        res = super().cleanup(success)

        return res
