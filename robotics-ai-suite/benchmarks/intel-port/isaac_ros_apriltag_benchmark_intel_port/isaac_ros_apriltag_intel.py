#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

"""Performance test for apriltag_ros AprilTagNode on Intel platforms."""

import os

from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode

from ros2_benchmark import ImageResolution, ROS2BenchmarkConfig, ROS2BenchmarkTest

IMAGE_RESOLUTION = ImageResolution.HD
ROSBAG_PATH = 'datasets/r2b_dataset/r2b_storage'


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    """Parse an integer environment variable with clamping."""
    raw = os.environ.get(name, str(default))
    try:
        return max(int(raw), minimum)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    """Parse a float environment variable with clamping."""
    raw = os.environ.get(name, str(default))
    try:
        return max(float(raw), minimum)
    except (TypeError, ValueError):
        return default


APRILTAG_FAMILY = os.environ.get('APRILTAG_FAMILY', '36h11')
APRILTAG_SIZE_METERS = _env_float('APRILTAG_SIZE_METERS', 0.162, minimum=0.01)

R2B_PUBLISHER_UPPER_FPS = _env_float('R2B_PUBLISHER_UPPER_FPS', 80.0)
R2B_PUBLISHER_LOWER_FPS = _env_float('R2B_PUBLISHER_LOWER_FPS', 10.0)
R2B_PLAYBACK_BUFFER_SIZE = _env_int('R2B_PLAYBACK_BUFFER_SIZE', 80, minimum=1)


def launch_setup(container_prefix, container_sigterm_timeout):
    """Generate launch description for apriltag_ros benchmarking."""
    namespace = TestAprilTagNodeIntel.generate_namespace()

    apriltag_config = {
        'image_transport': 'raw',
        'family': APRILTAG_FAMILY,
        'size': APRILTAG_SIZE_METERS,
    }

    nodes = [
        ComposableNode(
            name='DataLoaderNode',
            namespace=namespace,
            package='ros2_benchmark',
            plugin='ros2_benchmark::DataLoaderNode',
            remappings=[
                ('hawk_0_left_rgb_image', 'data_loader/image'),
                ('hawk_0_left_rgb_camera_info', 'data_loader/camera_info'),
            ],
        ),
        ComposableNode(
            name='PrepResizeNode',
            namespace=namespace,
            package='image_proc',
            plugin='image_proc::ResizeNode',
            parameters=[{
                'width': IMAGE_RESOLUTION['width'],
                'height': IMAGE_RESOLUTION['height'],
                'use_scale': False,
            }],
            remappings=[
                ('image/image_raw', 'data_loader/image'),
                ('image/camera_info', 'data_loader/camera_info'),
                ('resize/image_raw', 'buffer/image'),
                ('resize/camera_info', 'buffer/camera_info'),
            ],
        ),
        ComposableNode(
            name='PlaybackNode',
            namespace=namespace,
            package='ros2_benchmark',
            plugin='ros2_benchmark::PlaybackNode',
            parameters=[{
                'data_formats': [
                    'sensor_msgs/msg/Image',
                    'sensor_msgs/msg/CameraInfo',
                ],
            }],
            remappings=[
                ('buffer/input0', 'buffer/image'),
                ('input0', 'image'),
                ('buffer/input1', 'buffer/camera_info'),
                ('input1', 'camera_info'),
            ],
        ),
        ComposableNode(
            name='MonitorNode',
            namespace=namespace,
            package='ros2_benchmark',
            plugin='ros2_benchmark::MonitorNode',
            parameters=[{
                'monitor_data_format': 'apriltag_msgs/msg/AprilTagDetectionArray',
            }],
            remappings=[('output', 'apriltag_detections')],
        ),
        ComposableNode(
            name='AprilTagNode',
            namespace=namespace,
            package='apriltag_ros',
            plugin='AprilTagNode',
            parameters=[apriltag_config],
            remappings=[
                ('image_rect', 'image'),
                ('detections', 'apriltag_detections'),
            ],
        ),
    ]

    container = ComposableNodeContainer(
        name='container',
        namespace=namespace,
        package='rclcpp_components',
        executable='component_container_mt',
        prefix=container_prefix,
        sigterm_timeout=container_sigterm_timeout,
        composable_node_descriptions=nodes,
        output='screen',
    )

    return [container]


def generate_test_description():
    return TestAprilTagNodeIntel.generate_test_description_with_nsys(launch_setup)


class TestAprilTagNodeIntel(ROS2BenchmarkTest):
    """Performance test for apriltag_ros AprilTagNode on Intel."""

    config = ROS2BenchmarkConfig(
        benchmark_name='Isaac ROS® AprilTag Benchmark (Intel)',
        input_data_path=ROSBAG_PATH,
        input_data_start_time=3.0,
        input_data_end_time=3.5,
        publisher_upper_frequency=R2B_PUBLISHER_UPPER_FPS,
        publisher_lower_frequency=R2B_PUBLISHER_LOWER_FPS,
        playback_message_buffer_size=R2B_PLAYBACK_BUFFER_SIZE,
        custom_report_info={
            'data_resolution': IMAGE_RESOLUTION,
            'apriltag_family': APRILTAG_FAMILY,
            'apriltag_size_m': APRILTAG_SIZE_METERS,
        },
    )

    def test_benchmark(self):
        self.run_benchmark()
