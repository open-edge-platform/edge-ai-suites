#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

"""
Performance test for CenterPose Pose Estimation on Intel CPU/iGPU.

Uses OpenVINO Runtime for inference instead of NVIDIA® TensorRT/Triton.
The pipeline:
  DataLoaderNode → PrepResizeNode → PlaybackNode →
  CenterPoseOpenVINONode (encode+infer+decode) → MonitorNode

Required:
- Packages: ros2_benchmark, image_proc, isaac_ros_benchmark
- Models:   assets/models/centerpose_shoe/centerpose_shoe.xml
- Datasets: assets/datasets/r2b_dataset/r2b_storage
- Python:   openvino, numpy, opencv-python
"""

import os
import time

from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode

from ros2_benchmark import Resolution, ROS2BenchmarkConfig, ROS2BenchmarkTest
from ros2_benchmark import ImageResolution

IMAGE_RESOLUTION = Resolution(1920, 1080)
NETWORK_RESOLUTION = Resolution(512, 512)
# Resize images to network resolution before inter-process transfer
# to minimize ROS message overhead (512x512x3=786KB vs 1920x1080x3=6.2MB)
PIPELINE_RESOLUTION = NETWORK_RESOLUTION
ROSBAG_PATH = 'datasets/r2b_dataset/r2b_storage'


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    """Parse integer environment variable with clamping."""
    raw = os.environ.get(name, str(default))
    try:
        return max(int(raw), minimum)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    """Parse float environment variable with clamping."""
    raw = os.environ.get(name, str(default))
    try:
        return max(float(raw), minimum)
    except (TypeError, ValueError):
        return default


OV_DEVICE = os.environ.get('OV_DEVICE', os.environ.get('OPENVINO_DEVICE', 'CPU'))
OV_NUM_INFER_THREADS = _env_int('OV_NUM_INFER_THREADS', 0)
DEFAULT_OV_INIT_WAIT_SEC = _env_float('OV_INIT_WAIT_SEC', 3.0)

# Tune benchmark search space and buffering based on platform capability.
R2B_PUBLISHER_UPPER_FPS = _env_float('R2B_PUBLISHER_UPPER_FPS', 120.0)
R2B_PUBLISHER_LOWER_FPS = _env_float('R2B_PUBLISHER_LOWER_FPS', 10.0)
R2B_PLAYBACK_BUFFER_SIZE = _env_int('R2B_PLAYBACK_BUFFER_SIZE', 100, minimum=1)


def launch_setup(container_prefix, container_sigterm_timeout):
    """Generate launch description for CenterPose benchmark on Intel."""

    # Resolve model path relative to the ros2_benchmark assets
    assets_root = os.path.join(
        os.environ.get('ISAAC_ROS_WS', os.path.expanduser('~/ros2_ws')),
        'src', 'ros2_benchmark', 'assets')
    model_path = os.path.join(assets_root, 'models', 'centerpose_shoe', 'centerpose_shoe.xml')

    data_loader_node = ComposableNode(
        name='DataLoaderNode',
        namespace=TestCenterPoseIntel.generate_namespace(),
        package='ros2_benchmark',
        plugin='ros2_benchmark::DataLoaderNode',
        remappings=[
            ('hawk_0_left_rgb_image', 'data_loader/image'),
            ('hawk_0_left_rgb_camera_info', 'data_loader/camera_info'),
        ],
    )

    prep_resize_node = ComposableNode(
        name='PrepResizeNode',
        namespace=TestCenterPoseIntel.generate_namespace(),
        package='image_proc',
        plugin='image_proc::ResizeNode',
        parameters=[{
            'width': PIPELINE_RESOLUTION['width'],
            'height': PIPELINE_RESOLUTION['height'],
            'use_scale': False,
        }],
        remappings=[
            ('image/image_raw', 'data_loader/image'),
            ('image/camera_info', 'data_loader/camera_info'),
            ('resize/image_raw', 'buffer/image'),
            ('resize/camera_info', 'buffer/camera_info'),
        ],
    )

    playback_node = ComposableNode(
        name='PlaybackNode',
        namespace=TestCenterPoseIntel.generate_namespace(),
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
    )

    monitor_node = ComposableNode(
        name='MonitorNode',
        namespace=TestCenterPoseIntel.generate_namespace(),
        package='ros2_benchmark',
        plugin='ros2_benchmark::MonitorNode',
        parameters=[{
            'monitor_data_format': 'vision_msgs/msg/Detection3DArray',
        }],
        remappings=[
            ('output', 'centerpose/detections'),
        ],
    )

    # CenterPose OpenVINO inference (C++ composable — intra-process, zero DDS hop)
    centerpose_node = ComposableNode(
        name='CenterPoseOpenVINONode',
        namespace=TestCenterPoseIntel.generate_namespace(),
        package='isaac_ros_benchmark',
        plugin='isaac_ros_benchmark::CenterPoseOpenVINONode',
        parameters=[{
            'model_path': model_path,
            'score_threshold': 0.3,
            'object_name': 'shoe',
            'network_width': NETWORK_RESOLUTION['width'],
            'network_height': NETWORK_RESOLUTION['height'],
            'openvino_device': OV_DEVICE,
            'num_infer_threads': OV_NUM_INFER_THREADS,
            'image_mean': [0.408, 0.447, 0.47],
            'image_stddev': [0.289, 0.274, 0.278],
        }],
        remappings=[
            ('image', 'image'),
            ('camera_info', 'camera_info'),
            ('centerpose/detections', 'centerpose/detections'),
        ],
    )

    composable_node_container = ComposableNodeContainer(
        name='container',
        namespace=TestCenterPoseIntel.generate_namespace(),
        package='rclcpp_components',
        executable='component_container_mt',
        prefix=container_prefix,
        sigterm_timeout=container_sigterm_timeout,
        composable_node_descriptions=[
            data_loader_node,
            prep_resize_node,
            playback_node,
            monitor_node,
            centerpose_node,
        ],
        output='screen',
    )

    return [composable_node_container]


def generate_test_description():
    return TestCenterPoseIntel.generate_test_description_with_nsys(launch_setup)


class TestCenterPoseIntel(ROS2BenchmarkTest):
    """Performance test for CenterPose on Intel CPU/iGPU."""

    config = ROS2BenchmarkConfig(
        benchmark_name='CenterPose Benchmark (Intel CPU/iGPU via OpenVINO Runtime)',
        input_data_path=ROSBAG_PATH,
        # Use a wider time window for more frames
        input_data_start_time=0.0,
        input_data_end_time=4.0,
        # Upper and lower bounds of peak throughput search window
        publisher_upper_frequency=R2B_PUBLISHER_UPPER_FPS,
        publisher_lower_frequency=R2B_PUBLISHER_LOWER_FPS,
        # The number of frames to be buffered
        playback_message_buffer_size=R2B_PLAYBACK_BUFFER_SIZE,
        custom_report_info={
            'data_resolution': IMAGE_RESOLUTION,
            'pipeline_resolution': PIPELINE_RESOLUTION,
            'network_resolution': NETWORK_RESOLUTION,
            'openvino_device': OV_DEVICE,
            'num_infer_threads': OV_NUM_INFER_THREADS,
        },
    )

    # Wait for model to initialize
    OV_INIT_WAIT_SEC = DEFAULT_OV_INIT_WAIT_SEC

    def pre_benchmark_hook(self):
        time.sleep(self.OV_INIT_WAIT_SEC)

    def test_benchmark(self):
        self.run_benchmark()
