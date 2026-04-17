# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

import pytest
import sys

sys.path.insert(0, '../../src/pyrealsense2_ai_demo')

from images_capture import VideoCapWrapper, DirReader, ImreadWrapper

# Test 1: Video wrapper - get source type test
# -------------------------------------------
def test_videocapwrapper_get_source_type():
    videocapwrap = VideoCapWrapper('../../videos/How_People_Walk.mp4', loop=True)
    assert videocapwrap.get_type() == "VIDEO"


# Test 2: Read DIR - get source type test
# -------------------------------------------

def test_dirreader_get_source_type():
    dirreader = DirReader('../../images/', loop=True)
    assert dirreader.get_type() == "DIR"

# Test 3: Image - get source type test
# -------------------------------------------
def test_imreadwrapper_get_source_type():
    imreadwrap = ImreadWrapper('../../images/Realsense_D457_GMSL_Connection_to_Axiomtek.jpg', loop=True)
    assert imreadwrap.get_type() == "IMAGE"
