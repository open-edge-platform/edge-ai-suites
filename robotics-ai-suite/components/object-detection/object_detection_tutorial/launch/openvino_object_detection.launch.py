# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

import sys
import yaml
from pathlib import Path
from tempfile import NamedTemporaryFile
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, \
                           LogInfo, OpaqueFunction, Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_modified_yaml(device):
    try:
        template_path = Path(
            get_package_share_directory('object_detection_tutorial')) \
                                        / 'param' \
                                        / 'object_detection_pipeline.yaml'

        with template_path.open('r') as file:
            config = yaml.safe_load(file)

        config['Pipelines'][0]['infers'][0]['engine'] = device

        with NamedTemporaryFile(mode='w',
                                delete=False,
                                suffix='.yaml') as tmp_file:
            yaml.safe_dump(config, tmp_file)

        return tmp_file.name
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)

    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {e}")
        sys.exit(1)


def generate_launch_description(*args, **kwargs):

    device = LaunchConfiguration('device')
    supported_devices = ['NPU', 'GPU', 'CPU']

    def launch_nodes(context, *args, **kwargs):
        selected_device = context.launch_configurations['device']

        # Check if the provided device is supported
        if selected_device not in supported_devices:
            logger.error(f"Error: Unsupported device \
                         '{selected_device}'. Supported devices are: \
                            {supported_devices}")
            return [Shutdown(reason=f"Unsupported device '{selected_device}'")]

        modified_config_path = create_modified_yaml(selected_device)

        openvino_node = Node(
            package='openvino_node',
            executable='pipeline_with_params',
            name='pipeline_object',
            arguments=['-config', modified_config_path],
            remappings=[
                ('/openvino_toolkit/object/detected_objects',
                 '/ros2_openvino_toolkit/detected_objects'),
                ('/openvino_toolkit/object/images',
                 '/ros2_openvino_toolkit/image_rviz')
            ],
            output='screen'
        )

        return [openvino_node]

    return LaunchDescription([
        DeclareLaunchArgument(
            device,
            default_value='GPU',
            description='Inference device to use (e.g., NPU, GPU, CPU)'
        ),
        OpaqueFunction(function=launch_nodes),
        LogInfo(msg=[LaunchConfiguration('device'),
                     " device selected for inference"])
    ])


if __name__ == '__main__':
    ld = generate_launch_description()
