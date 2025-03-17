#
# Apache v2 license
# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""MQTT Publisher.
"""

import logging
import base64
import json
import os
import datetime
import numpy
import time

from utils.mqtt_client import MQTTClient
from utils import publisher_utils as utils

from gstgva import RegionOfInterest, Tensor, VideoFrame
from typing import List

DEBUG = False
LAYER_NAME = "classification"

class MQTTPublisher:
    """MQTT Publisher
    """

    def __init__(self, host, port, topic="edge_video_analytics_results", publish_frame=False, include_feature_vector=False, qos=0, protocol=4, tls=None):
        """Constructor
        """
        self.log = logging.getLogger('MQTT_PUBLISHER')
        self.log.setLevel(logging.INFO)
        self.log.debug(f"In {__name__}...")
        self.host = host
        self.port = port
        self.topic = topic
        self.publish_frame = publish_frame
        self.include_feature_vector = include_feature_vector
        self.qos = qos
        self.protocol = protocol

        self.frame_id = 0
        self.client = MQTTClient(self.host, self.port, self.topic, self.qos, self.protocol, tls)

    def process(self, frame: VideoFrame):
        """ Publish frame and metadata to mqtt broker
        """
        
        should_publish = False

        # Get buffer data
        with frame.data() as image:
            video_info = frame.video_info()
            metadata = {}
            utils.get_gva_meta_messages(frame, metadata)
            #metadata['gva_meta'] = utils.get_gva_meta_regions(frame)

            if not self.client.is_connected():
                self.log.error(f"Client is not connected to MQTT broker. Message not published. {metadata}")
                return

            metadata['frame_id'] = self.frame_id
            if os.getenv("ADD_UTCTIME_TO_METADATA","").lower() == "true" and "time" not in metadata:
                metadata["time"] = int(datetime.datetime.now(datetime.timezone.utc).timestamp()*1e9)
            self.frame_id += 1

            #Update metadata first
            image_format = video_info.to_caps().get_structure(0).get_value('format')
            metadata["img_format"]=image_format

            # Update final response (msg)   
            msg = dict()
            msg["metadata"]=metadata

            if self.publish_frame:
                #Channels
                if image_format == 'RGBA' or image_format == 'BGRA':
                    channels = 4
                elif image_format == 'GRAY8':
                    channels = 1
                else:
                    channels = 3
                #If raw frame, jpeg encode the image
                if video_info.to_caps().to_string().split(',')[0] == "video/x-raw":
                    image, _, _, _ = utils.encode_frame("jpeg", 85, frame=image, height=video_info.height,
                                                    width=video_info.width, channels=channels, meta_data=metadata)
                    image = image[1]

                base64_enc_frame = base64.b64encode(image.tobytes()).decode('utf-8')
                msg["blob"]=base64_enc_frame
            else:
                msg["blob"] = ""

            if self.include_feature_vector:
                regions: List[RegionOfInterest] = frame.regions()

                # Iterate over Regions
                for roi in regions:
                    tensors: List[Tensor] = roi.tensors()

                    # Iterate over Tensors
                    for tensor in tensors:

                        # Gather tensor information
                        tensor_data: numpy.ndarray = (
                            tensor.data()
                            if tensor.precision() != Tensor.PRECISION.UNSPECIFIED
                            else numpy.ndarray([0])
                        )

                        # Only process classification frames
                        if tensor.name() != LAYER_NAME:
                            continue

                        tensor_meta = {
                            "dims": [tensor.dims()],
                            "name": [tensor.name()]
                        }
                        tensor_data=[base64.b64encode(tensor.data().tobytes()).decode('utf-8')]
                        msg["metadata"]["tensor_metadata"] = tensor_meta
                        msg["tensor_blobs"] = tensor_data
                        should_publish = True

                        # TODO: This implementation only publish embeddings for the last Region of Interest (ROI).
                        # When there is a single ROI, the implementation is correct.
                        # But for multiple ROIs, it will miss the objects other than the last one.
                        # The fix requires changes in feature-matching message handling as well.
            else:
                msg["metadata"]["tensor_metadata"] = {"dims":[], "name": []}
                msg["tensor_blobs"]=[]

            msg = json.dumps(msg)
            
            if (should_publish):
                self.log.info(f'Publishing message to: {self.topic}')
                self.client.publish(self.topic, payload=msg)

            # Discarding publish message
            del msg

        return True