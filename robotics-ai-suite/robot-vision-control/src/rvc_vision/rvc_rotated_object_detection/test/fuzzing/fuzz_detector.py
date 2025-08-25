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

import atheris

import cv2
import os
import sys

from rvc_rotated_object_detection.rotated_object_detection_parameters import object_detection
from rvc_rotated_object_detection.object_detection import Detector
from std_msgs.msg import Header

class FuzzDetector(Detector):
   def __init__(self, orb, roi):
      super().__init__(orb, roi)

   def fuzz_initialize_object(self, data):
      # Not checked here but it might beneficial to add a check here to be
      # sure that data is large enough. This can be an issue with APIs like:
      #   - def ConsumeInt(int: bytes)
      #   - def ConsumeBytes(count: int)
      fdp = atheris.FuzzedDataProvider(data)
      # Generate random inputs
      obj_name = fdp.ConsumeIntInRange(0, 100)
      thickness = fdp.ConsumeIntInRange(1, 100)
      nfeatures = fdp.ConsumeIntInRange(1, 500)

      resources_dir = os.path.join(os.path.dirname(__file__), '../resources')
      image_path = os.path.join(resources_dir, 'robot.png')
      try:
         # Call the method with the fuzzed inputs
         self.initialize_object(obj_name, thickness, image_path, nfeatures)
         img = cv2.imread(os.path.join(resources_dir, 'test1.jpg'))
         header = Header()
         detections, corners = self.detect(img, header)
      except ValueError:
         # Handle expected exceptions here
         pass

# Enable coverage instrumentation only for this function (and recursively)
@atheris.instrument_func
def first_fuzz_test(data):
   params = object_detection.Params()
   detector = FuzzDetector(params.orb, params.roi)
   detector.fuzz_initialize_object(data)

def main():
   atheris.Setup(sys.argv, first_fuzz_test)
   atheris.Fuzz()

if __name__ == "__main__":
    main()
