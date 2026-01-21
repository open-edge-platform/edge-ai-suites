# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from gstgva import VideoFrame

class DetectionFilter:
    def __init__(self, *args, **kwargs):
        # gvapython passes arg=[...] as positional args to __init__(self, *args)
        # so we accept one optional arg for skip_n_frames
        print("DetectionFilter initialized.")

    def process(self, frame:VideoFrame) -> bool:
        """
        Called for each frame. Skips processing for the first N frames
        as specified by skip_n_frames.
        """
        # If JSON meta exists, conversions ran and there were detections
        # Depending on your DLS version, you may access messages/tensors/metadata;
        # the simplest proxy is to check that regions() yields at least one ROI.
        return next(frame.regions(), None) is not None