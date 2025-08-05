# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

import os
import pytest

import rclpy
from std_msgs.msg import Header

import cv2

from numpy.testing import assert_allclose

from rvc_rotated_object_detection.object_detection import Detector
from rvc_rotated_object_detection.rotated_object_detection_parameters import object_detection
from rvc_vision_messages.msg import RotatedBB, RotatedBBList

@pytest.fixture
def resources_dir():
    return os.path.join(os.path.dirname(__file__), 'resources')

@pytest.fixture
def detector(resources_dir: str):
    params = object_detection.Params()
    detector = Detector(params.orb, params.roi)
    detector.initialize_object(0, 0, os.path.join(resources_dir, 'robot.png'), 500)
    return detector

def test_image(detector: Detector, resources_dir: str):
    img = cv2.imread(os.path.join(resources_dir, 'test1.jpg'))
    header = Header()
    detections, corners = detector.detect(img, header)
    assert len(detections.rotated_bb_list) == 1
    detection = detections.rotated_bb_list[0]
    assert detection.object_id == 0

    img = cv2.imread(os.path.join(resources_dir, 'test2.jpg'))
    detections, corners = detector.detect(img, header)
    assert len(detections.rotated_bb_list) == 1
    detection = detections.rotated_bb_list[0]

    img = cv2.imread(os.path.join(resources_dir, 'test3.jpg'))
    detections, corners = detector.detect(img, header)
    assert len(detections.rotated_bb_list) == 1
    detection = detections.rotated_bb_list[0]

    img = cv2.imread(os.path.join(resources_dir, 'test4.jpg'))
    detections, corners = detector.detect(img, header)
    assert len(detections.rotated_bb_list) == 1
    detection = detections.rotated_bb_list[0]

    img = cv2.imread(os.path.join(resources_dir, 'test5.jpg'))
    detections, corners = detector.detect(img, header)
    assert len(detections.rotated_bb_list) == 1
    detection = detections.rotated_bb_list[0]

def test_roi(detector: Detector, resources_dir: str):
    img = cv2.imread(os.path.join(resources_dir, 'test3.jpg'))
    header = Header()
    detections, corners = detector.detect(img, header)
    params = object_detection.Params()
    roi = params.roi
    roi.crop_left = 200
    roi.crop_right = 200
    roi.crop_top = 200
    roi.crop_bottom = 200
    detector.set_params(detector.orb_params, roi)
    cropped_detections, cropped_corners = detector.detect(img, header)
    assert_allclose(corners, cropped_corners, rtol=0.05)
