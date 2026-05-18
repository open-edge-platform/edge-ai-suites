#!/usr/bin/env python3
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import time
from pathlib import Path
import copy
import cv2
import numpy as np
import pyrealsense2 as rs


class InvalidInput(Exception):

    def __init__(self, message):
        self.message = message


class OpenError(Exception):

    def __init__(self, message):
        self.message = message


class ImagesCapture:

    def read():
        raise NotImplementedError

    def get_distance(self, x, y):
        return None

    def fps():
        raise NotImplementedError

    def get_type():
        raise NotImplementedError


class ImreadWrapper(ImagesCapture):

    def __init__(self, input, loop):
        self.loop = loop
        if not os.path.isfile(input):
            raise InvalidInput("Can't find the image: {} ".format(input))
        self.image = cv2.imread(input, cv2.IMREAD_COLOR)
        if self.image is None:
            raise OpenError("Can't open the image from {}".format(input))
        self.can_read = True

    def read(self):
        if self.loop:
            return copy.deepcopy(self.image)
        if self.can_read:
            self.can_read = False
            return copy.deepcopy(self.image)
        return None

    def fps(self):
        return 1.0

    def get_type(self):
        return 'IMAGE'


class DirReader(ImagesCapture):

    def __init__(self, input, loop):
        self.loop = loop
        self.dir = input
        if not os.path.isdir(self.dir):
            raise InvalidInput("Can't find the dir by {}".format(input))
        self.names = sorted(os.listdir(self.dir))
        if not self.names:
            raise OpenError("The dir {} is empty".format(input))
        self.file_id = 0
        for name in self.names:
            filename = os.path.join(self.dir, name)
            image = cv2.imread(filename, cv2.IMREAD_COLOR)
            if image is not None:
                return
        raise OpenError("Can't read the first image from {}".format(input))

    def read(self):
        while self.file_id < len(self.names):
            filename = os.path.join(self.dir, self.names[self.file_id])
            print(filename)
            image = cv2.imread(filename, cv2.IMREAD_COLOR)
            self.file_id += 1
            if image is not None:
                return image
        if self.loop:
            self.file_id = 0
            while self.file_id < len(self.names):
                filename = os.path.join(self.dir, self.names[self.file_id])
                image = cv2.imread(filename, cv2.IMREAD_COLOR)
                self.file_id += 1
                if image is not None:
                    return image
        return None

    def fps(self):
        return 1.0

    def get_type(self):
        return 'DIR'


class VideoCapWrapper(ImagesCapture):

    def __init__(self, input, loop):
        self.loop = loop
        self.cap = cv2.VideoCapture()
        # Device nodes (e.g. /dev/video-isx031-a-0) are handled by CameraCapWrapper
        if input.startswith('/dev/'):
            raise InvalidInput("Device path - use CameraCapWrapper: {}".format(input))
        status = self.cap.open(input)
        if not status:
           raise InvalidInput("Can't open the video from {}".format(input))

    def read(self):
        status, image = self.cap.read()
        if not status:
            if not self.loop:
                return None
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            status, image = self.cap.read()
            if not status:
                return None
        return image

    def fps(self):
        return self.cap.get(cv2.CAP_PROP_FPS)

    def get_type(self):
        return 'VIDEO'

class RealSenseCapWrapper(ImagesCapture):
    def __init__(self, input, camera_resolution):

        status = False
        if input.isnumeric():
            self.id = int(input)
            self.ctx = rs.context()
            if len(self.ctx.devices) > 0 and len(self.ctx.devices) > self.id:
                self.pipeline = rs.pipeline()
                self.id = int(input)
                self.device = self.ctx.devices[self.id]
                sensor_sn = self.device.get_info(rs.camera_info.serial_number)
                self.config = rs.config()
                self.config.enable_device(sensor_sn)
                self.config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
                self.config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
                self.pipeline.start(self.config)
                self.depth_frame = None
                status = True

        if not status:
            raise InvalidInput("Can't find the RS camera {}".format(input))

    def read(self):
        frames = self.pipeline.wait_for_frames()
        color_frame = frames.get_color_frame()
        self.depth_frame = frames.get_depth_frame()

        if  color_frame:
            color_frame = np.asanyarray(color_frame.get_data())

        return color_frame

    def get_distance(self, x, y):
        if self.depth_frame is not None:
            dist = self.depth_frame.get_distance(int(x), int(y));
            return dist

        return None

    def fps(self):
        return 0

    def get_type(self):
        return 'CAMERA RS'

class CameraCapWrapper(ImagesCapture):

    def __init__(self, input, camera_resolution, fourcc=None):

        self.cap = cv2.VideoCapture()
        # Accept both integer indices ("0") and device paths ("/dev/video-isx031-a-0").
        # OpenCV's V4L2 backend cannot open devices by symlink name and falls back to
        # FFMPEG. Resolve any symlink to /dev/videoN and pass as an integer so V4L2
        # is used consistently across all camera nodes.
        try:
            device = int(input)
            is_ipu = False
        except ValueError:
            if not os.path.exists(input):
                raise InvalidInput("Can't find the camera {}".format(input))
            real = os.path.realpath(input)    # /dev/video-isx031-d-2 → /dev/video36
            basename = os.path.basename(real)
            if basename.startswith('video') and basename[5:].isdigit():
                device = int(basename[5:])    # pass integer; forces V4L2 backend
            else:
                device = real
            is_ipu = True

        status = self.cap.open(device, cv2.CAP_V4L2)
        # Do NOT set BUFFERSIZE=1 — IPU/CSI drivers require at least 3 MMAP buffers
        # for stable streaming; constraining to 1 causes frame drops on some nodes.
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_resolution[1])
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        if fourcc:
            # Caller-supplied FOURCC (e.g. 'YUYV', 'MJPG', 'UYVY', 'NV12') wins.
            code = fourcc.upper().ljust(4)[:4]
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*code))
            if not is_ipu:
                self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        elif is_ipu:
            # ISX031 and similar IPU cameras output UYVY by default
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'UYVY'))
        else:
            # MJPG and autofocus are only applicable to indexed USB cameras
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        if not status:
            raise OpenError("Can't open the camera from {}".format(input))

        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        actual_w   = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h   = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fcc = int(self.cap.get(cv2.CAP_PROP_FOURCC))
        fcc_str    = ''.join(chr((actual_fcc >> 8 * i) & 0xFF) for i in range(4)) if actual_fcc else '?'
        backend    = self.cap.getBackendName()
        print(f"[CAMERA] {input} (opened as {device}): backend={backend} "
              f"{actual_w}x{actual_h}@{actual_fps:.0f}fps fourcc={fcc_str}")

    def read(self):
        status, image = self.cap.read()
        if not status:
            return None
        return image

    def fps(self):
        return self.cap.get(cv2.CAP_PROP_FPS)

    def get_type(self):
        return 'CAMERA'

class VideoCapture():
    def __init__(self, input, loop=True, camera_resolution=(1280, 720), fourcc=None):

        self.inputs = input.split(',')
        self.nb_inputs = len(self.inputs)
        self.input_index = -1
        self.loop = loop
        self.camera_resolution = camera_resolution
        self.fourcc = fourcc
        self.next()

    def read(self):
        if self.reader is not None:
            return self.reader.read()
        return None

    def next(self):

        self.reader = None

        while self.reader == None:
            errors = {InvalidInput: [], OpenError: []}

            self.input_index = (self.input_index+1) % self.nb_inputs
            input = self.inputs[self.input_index]

            for reader in (ImreadWrapper, DirReader, RealSenseCapWrapper, VideoCapWrapper):
                try:
                    self.reader = reader(input, self.loop)
                    if self.reader is not None:
                        return
                except (InvalidInput, OpenError) as e:
                    errors[type(e)].append(e.message)
            try:
                self.reader = CameraCapWrapper(input, self.camera_resolution, fourcc=self.fourcc)
                if self.reader is not None:
                    return

            except (InvalidInput, OpenError) as e:
                errors[type(e)].append(e.message)
            if not errors[OpenError]:
                print(*errors[InvalidInput], file=sys.stderr, sep='\n')
            else:
                print(*errors[OpenError], file=sys.stderr, sep='\n')

    def get_distance(self, x, y):
        if self.reader is not None:
            return self.reader.get_distance(x,y)
        return None
