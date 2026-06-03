"""
Custom DL Streamer pipeline element for adding PTP-synchronized timestamps.

This script defines a class, `PTPFrameTimeStamp`, which can be used as a custom
processing block within a DL Streamer pipeline. Its primary function is to
capture the current system time, which is assumed to be synchronized via PTP,
and inject it as a JSON message into the metadata of each video frame that
passes through it.
"""

# 
# Copyright (C) 2026 Intel Corporation. 
# 
# SPDX-License-Identifier: Apache-2.0 
#

import json
from time import ctime, sleep
import ntplib
import requests
from datetime import datetime

class PTPFrameTimeStamp:
    """
    A custom pipeline element to add a PTP-synchronized timestamp to a frame.

    This class is designed to be instantiated by a pipeline framework. The `process`
    method is called for each frame, where it adds a 'ptp_timestamp' field to the
    frame's metadata.
    """
    def __init__(self):
        """Initializes the PTPFrameTimeStamp instance."""
        pass

    def _get_timestamp(self):
        """
        Get the current PTP-synchronized timestamp.

        This method returns the current time as a Unix timestamp (seconds since epoch).
        It relies on the underlying system clock being accurately synchronized by a
        PTP service like ptp4l and phc2sys.

        Returns:
            float: The current Unix timestamp.
        """
        return datetime.now().timestamp()

    def process(self, frame):
        """
        Process a frame and add a timestamp to its metadata.

        This is the main entry point called by the pipeline for each frame.
        It retrieves the current timestamp and adds it to the frame's metadata
        as a JSON string.

        Args:
            frame: The frame object from the pipeline.

        Returns:
            bool: True to indicate successful processing.
        """
        frame.add_message(json.dumps({'ptp_timestamp': self._get_timestamp()}))
        return True
