# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

import cv2
import os
import sys

import atheris

sys.path.insert(0, 'src/pyrealsense2_ai_demo')

from images_capture import ImreadWrapper

# Enable coverage instrumentation only for this function (and recursively)
@atheris.instrument_func
def fuzz_test_imreadwrapper(data):
   fdp = atheris.FuzzedDataProvider(data)
   data = fdp.ConsumeString(sys.maxsize)

   try:
      imreadwrap = ImreadWrapper(data, loop=True)
         
   except:
      pass

def main():
   atheris.Setup(sys.argv, fuzz_test_imreadwrapper)
   atheris.Fuzz()

if __name__ == "__main__":
    main()
