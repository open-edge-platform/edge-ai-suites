# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import string
import cv2
import sys
import time
import numpy as np
from queue import Queue
from loguru import logger
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

import pyrealsense2 as rs

from PySide6 import QtGui
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QFile, QThread, Signal, Slot, QPointF
from PySide6.QtUiTools import QUiLoader
from PySide6.QtGui import QPixmap, QFont, QPalette, QLinearGradient
import qtawesome as qta

from utils.common import draw_rect, draw_points

# add asr
from utils.funasr_client import ThreadClient
from translate import Translator

# add phi3
from executor import *

prompt_from_ui=""

class CameraStreamThread(QThread):
    updatePixmap = Signal(dict)

    def __init__(self, cam_w=1280, cam_h=720):
        super().__init__()
        self._cam_type = "REALSENSE"
        self._run_flag = True
        self.cam_w = cam_w
        self.cam_h = cam_h
        self.depth_intrinsics = None
        self.color_camera_matrix = None
        self.color_distortion_coefficient = None

    def _setup_realsense_camera(self):
        pipeline = rs.pipeline()
        config = rs.config()

        # Get device product line for setting a supporting resolution
        pipeline_wrapper = rs.pipeline_wrapper(pipeline)
        pipeline_profile = config.resolve(pipeline_wrapper)
        device = pipeline_profile.get_device()
        device_product_line = str(device.get_info(rs.camera_info.product_line))

        found_rgb = False
        for s in device.sensors:
            if s.get_info(rs.camera_info.name) == 'RGB Camera':
                found_rgb = True
                break
        if not found_rgb:
            logger.error("[REALSENSE] The demo requires Depth camera with Color sensor")
            exit(0)

        config.enable_stream(
            rs.stream.depth,
            self.cam_w,
            self.cam_h,
            rs.format.z16,
            30
        )
        if device_product_line == 'L500':
            config.enable_stream(
                rs.stream.color,
                960,
                540,
                rs.format.bgr8,
                30
            )
        else:
            config.enable_stream(
                rs.stream.color,
                self.cam_w,
                self.cam_h,
                rs.format.bgr8,
                30
            )
        profile = pipeline.start(config)

        color_profile= rs.video_stream_profile(profile.get_stream(rs.stream.color))
        color_intrinsic = color_profile.get_intrinsics()
        self.color_camera_matrix = np.array([
            [color_intrinsic.fx, 0, color_intrinsic.ppx],
            [0, color_intrinsic.fy, color_intrinsic.ppy],
            [0, 0, 1]
        ])
        self.color_distortion_coefficient = np.array([
            color_intrinsic.coeffs[0],
            color_intrinsic.coeffs[1],
            color_intrinsic.coeffs[2],
            color_intrinsic.coeffs[3],
            color_intrinsic.coeffs[4],
        ])

        depth_sensor = profile.get_device().first_depth_sensor()
        depth_scale = depth_sensor.get_depth_scale()
        depth_profile = rs.video_stream_profile(
            profile.get_stream(rs.stream.depth))
        depth_intrinsics = depth_profile.get_intrinsics()
        align_to = rs.stream.color
        self.align = rs.align(align_to)
        self.decimate = rs.decimation_filter()
        self.decimate.set_option(rs.option.filter_magnitude, 2 ** 0)
        self.filters = [
            # rs.disparity_transform(),
            rs.spatial_filter(),
            rs.temporal_filter(),
            # rs.disparity_transform(False)
        ]
        self.hole_filling = rs.hole_filling_filter()
        return pipeline, depth_scale, depth_intrinsics

    def run(self):
        try:
            if self._cam_type == "REALSENSE":
                pipeline, depth_scale, depth_intrinsics = self._setup_realsense_camera()
            else:
                raise RuntimeError("Not supported camera type")

            while self._run_flag and pipeline:
                frames = pipeline.wait_for_frames()
                depth_frame = frames.get_depth_frame()
                color_frame = frames.get_color_frame()
                # depth_frame = self.hole_filling.process(depth_frame)
                depth_frame = self.decimate.process(depth_frame)
                # if len(self.filters) > 0:
                #     for f in self.filters:
                #         depth_frame = f.process(depth_frame)

                if not depth_frame or not color_frame:
                    continue
                
                color_image = np.asanyarray(color_frame.get_data())
                depth_image = np.asanyarray(depth_frame.get_data())

                frame_data = {
                    'color_frame': color_image,
                    'depth_frame': depth_image,
                    'depth_scale': depth_scale,
                    'depth_intrinsics': depth_intrinsics
                }
                self.updatePixmap.emit(frame_data)

        except Exception as error:
            logger.error(f"[REALSENSE] {error}")


class MainThread(QThread):
    updateInferenceResult = Signal(str)
    updateFaultInferenceResult = Signal(str)
    updateInferenceImg = Signal(np.ndarray)
    updateMicResult = Signal(str)

    def __init__(self, color_frame):
        super().__init__()
        self.max_attempts = 3
        self.color_frame = None
        self.depth_frame = None
        self.depth_scale = None
        self.depth_intrinsics = None

        # phi3 Inference thread
        self.inference_thread = InferenceThread(input_queue, input_lock, output_queue, output_lock)
        self.inference_thread.start()

        self.translator = Translator(from_lang="zh",to_lang="en")

    def update_image_frame(self, color_frame, depth_frame, depth_scale, depth_intrinsics):
        self.color_frame = color_frame
        self.depth_frame = depth_frame
        self.depth_scale = depth_scale
        self.depth_intrinsics = depth_intrinsics

    def run(self):
        self.updateInferenceResult.emit("")
        while True:
            global prompt_from_ui
            if prompt_from_ui == "":
                time.sleep(0.1)
            else:
                input_prompt = prompt_from_ui
                trans_begin_time = time.time()
                input_prompt = self.translator.translate(input_prompt)
                trans_end_time = time.time()
                logger.info(f"trans time: {trans_end_time-trans_begin_time}s")
                self.updateMicResult.emit(input_prompt)
                prompt_from_ui = ""

                vlm_begin_time = time.time()
                status, obj_info = get_obj_info(input_prompt, self.color_frame, self.depth_frame, self.depth_scale, self.depth_intrinsics)
                vlm_end_time = time.time()
                logger.info(f"VLM time: {vlm_end_time-vlm_begin_time}s")
                if status == 'SUCCESS':
                    inf_result_image = self.inference_thread.getInfResultImg()
                    self.updateInferenceImg.emit(inf_result_image)

                    for i in range(self.max_attempts):
                        lm_begin_time = time.time()
                        content = gen_code_1(input_prompt, obj_info, logger)
                        lm_end_time = time.time()
                        logger.info(f"LM code_gen time {i}: {lm_end_time-lm_begin_time}s")
                        if content is None:
                            continue
                        self.updateInferenceResult.emit(content)
                        result = execute_code_snippets(content, logger)
                        if result:
                            input_prompt = ""
                            break
                    if i < self.max_attempts:
                        logger.info(f"Primitive generated & executed successfully in {i + 1} trial!")
                    else:
                        logger.info("Max attempts reached!")
                else:
                    logger.info(f"The input has error {status}, please adjust your prompt!")
                    self.updateFaultInferenceResult.emit("")
                input_prompt = ""


class MainWindow(QWidget):
    def __init__(self, ui_file, parent=None):
        super(MainWindow, self).__init__()
        ui_file = QFile(ui_file)
        ui_file.open(QFile.ReadOnly)

        loader = QUiLoader()
        self.window = loader.load(ui_file)
        ui_file.close()

        # UI configs
        self.display_width = 540
        self.display_height = 240

        # Variable
        self.debug = True
        self.promptText = "Please input your prompt ..."
        self.isInferencingRunning = True  # check inference state

        # ASR microphone
        self._setup_asr_audio_devices()

        # Camera thread
        self.xymin = None
        self.cameraFrame = None
        self.depthFrame = None
        self.depthScale = None
        self.depthIntrinsics = None
        self.inferenceColorFrame = None
        self.inferenceDepthFrame = None

        self.camera_width = 1280
        self.camera_height = 720
        self.cameraThread = CameraStreamThread(self.camera_width, self.camera_height)
        self.cameraThread.updatePixmap.connect(self.UpdateCameraStream)

        # main process
        self.mainThread = MainThread(self.cameraFrame)
        self.mainThread.updateInferenceResult.connect(self.UpdateInferenceResult)
        self.mainThread.updateInferenceImg.connect(self.UpdateInfereceResultFrame)
        self.mainThread.updateFaultInferenceResult.connect(self.UpdateFaultInfereceResult)
        self.mainThread.updateMicResult.connect(self.UpdateMicResult)
        self.mainThread.start()

        # Show UI
        self._setup_ui()
        self._setup_ui_background()
        self.window.show()

        self.cameraThread.start()

    def _setup_ui_background(self):
        backgroundPalette = QPalette()
        backgroundPalette.setColor(QPalette.Normal, QPalette.Window, "#F7FDFF")
        self.window.setAutoFillBackground(True)
        self.window.setPalette(backgroundPalette)

    def _setup_asr_audio_devices(self):
        self.asr_inference_thread = ThreadClient(host="localhost")
        self.asr_inference_thread.start()
        self.asr_inference_thread.pause()
        self.asr_inference_thread.asr_input_text=""
        self.asr_inference_thread.asr_input_text_full=""

    def _write_app_status(self, status, color, size):
        self.window.appStatusLabel.setText(status)
        self.window.appStatusLabel.setStyleSheet(f'color: {color};')
        self.window.appStatusLabel.setFont(QFont('Times', size))

    def _write_debug_result_label(self, status, color, size):
        self.window.debugResultLabel.setText(status)
        self.window.debugResultLabel.setStyleSheet(f'color: {color};')
        self.window.debugResultLabel.setFont(QFont('Times', size))

    def _setup_logo_label(self):
        logo_img = cv2.imread("./images/core-ultra.png")
        logo_pixmap = self._convert_image_to_pixmap(logo_img, 81, 81)
        self.window.logoLabel.setPixmap(logo_pixmap)

    def _setup_ui(self):
        self._setup_logo_label()
        self.window.inferencingStatusData.setText("Completed")
        self.window.POIDistanceData.setText("-1.0")
        self.window.textPromptLineEdit.setText(self.promptText)
        self.window.confidenceLineEdit.setText("0.8")
        self.window.textConfidenceLineEdit.setText("0.5")
        self.window.submitPushButton.clicked.connect(self.submitButtonClicked)
        self.window.moveToPushButton.clicked.connect(
            self.moveToPushButtonClicked)
        self.window.visualizationCheckBox.toggle()
        self.window.visualizationCheckBox.stateChanged.connect(self.onVisualizationChecked)
        self.window.boxXMinLineEdit.setText("460")
        self.window.boxYMinLineEdit.setText("220")
        self.window.boxXMaxLineEdit.setText("375")
        self.window.boxYMaxLineEdit.setText("280")
        self.window.robotFrameXLineEdit.setText("260")
        self.window.robotFrameYLineEdit.setText("0")
        mic_icon = qta.icon('fa5s.microphone-alt')
        self.window.micPushButton.setIcon(mic_icon)
        self.window.micPushButton.clicked.connect(self.micButtonClicked)

    def onVisualizationChecked(self, state):
        if state == Qt.CheckState.Unchecked.value:
            self.debug = False
        elif state == Qt.CheckState.Checked.value:
            self.debug = True

    @Slot()
    def UpdateInferenceResult(self, result_str):
        self._write_app_status(result_str, "green", 10)

    @Slot()
    def updateInferenceState(self, state):
        self.window.inferencingStatusData.setText(
            "Running" if state['isRunning'] else "Completed")
        self.window.POIDistanceData.setText(
            str(round(state['POIDistance'], 2)))
        self._write_app_status(state['status'], "red" if state['isRunning'] == False and state['POIDistance'] == -1.0 else "green")

    @Slot()
    def micButtonClicked(self):
        if self.asr_inference_thread.input_running == False:
            self.window.micPushButton.setStyleSheet('background-color: green;')
            self.asr_inference_thread.resume()
            logger.debug("start record...")
        else:
            if self.asr_inference_thread.asr_input_flag == False:
                if self.asr_inference_thread.asr_input_text != "":
                    logger.debug(" mic result not ready to read !!! ")
                else:
                    logger.debug(" mic input is empty ")
                    self.window.micPushButton.setStyleSheet('background-color: white;')
                    self.asr_inference_thread.pause()
                return
            self.window.micPushButton.setStyleSheet('background-color: white;')
            self.asr_inference_thread.pause()
            input_str = self.asr_inference_thread.asr_input_text
            self.asr_inference_thread.asr_input_flag = False
            self.asr_inference_thread.asr_input_text = ""
            self.asr_inference_thread.asr_input_text_full = ""
            logger.debug("stop record...")
            logger.debug(f"input_text: {input_str}")
            self._write_app_status("Finding object specified by user ...", "blue", 30)
            self._write_debug_result_label("Waiting for detection result ... ", "blue", 30)
            global prompt_from_ui
            prompt_from_ui = input_str

    @Slot(str)
    def UpdateMicResult(self, result):
        self.window.textPromptLineEdit.setText(result)

    @Slot()
    def moveToPushButtonClicked(self):
        x = float(self.window.xCoordinateLineEdit.text())
        y = float(self.window.yCoordinateLineEdit.text())
        z = float(self.window.zCoordinateLineEdit.text())
        objLocation={
            "x": x,
            "y": y,
            "z": z
        }
        self.moveQueue.put(objLocation)

    @Slot()
    def submitButtonClicked(self):
        if self.window.textPromptLineEdit.text() != self.promptText:
            if self.window.textPromptLineEdit.text() != "":
                self._write_app_status("Finding object specified by user ...", "blue", 30)
                self._write_debug_result_label("Waiting for detection result ... ", "blue", 30)
                global prompt_from_ui
                prompt_from_ui = self.window.textPromptLineEdit.text()
                logger.debug(f"prompt from input text: {self.window.textPromptLineEdit.text()}")
            else:
                logger.debug("Please input your prompt ...")
        else:
            logger.debug("Please input your prompt ...")

    @Slot(dict)
    def UpdateCameraStream(self, frame_data):
        self.cameraFrame = frame_data['color_frame']
        self.depthFrame = frame_data['depth_frame']
        self.depthScale = frame_data['depth_scale']
        self.depthIntrinsics = frame_data['depth_intrinsics']

        self.mainThread.update_image_frame(self.cameraFrame, self.depthFrame, self.depthScale, self.depthIntrinsics)

        streamDepthFrame = cv2.applyColorMap(cv2.convertScaleAbs(
            self.depthFrame, alpha=0.03), cv2.COLORMAP_JET)
        
        xmin = int(self.window.boxXMinLineEdit.text())
        ymin = int(self.window.boxYMinLineEdit.text())
        xmax = int(self.window.boxXMinLineEdit.text()) + int(self.window.boxXMaxLineEdit.text())
        ymax = int(self.window.boxYMinLineEdit.text()) + int(self.window.boxYMaxLineEdit.text())
        self.xymin = (xmin, ymin)

        streamColorFrame = self.cameraFrame.copy()
        if self.debug:
            for i in range(self.camera_height):
                streamColorFrame = cv2.circle(streamColorFrame, (int(self.camera_width/2), int(i)), 2, (0,0,255), 2)
            draw_rect(streamColorFrame, coordinates=[xmin, ymin, xmax, ymax])
            draw_points(streamColorFrame,(int(self.camera_width/2), int(self.camera_height/2)), 2, (0, 255, 0))

        # This is to get the bounding box image to get inference running ...
        self.inferenceColorFrame = self.cameraFrame[ymin:ymax, xmin:xmax]

        color_qt_img = self._convert_image_to_pixmap(
            streamColorFrame, self.display_width, self.display_height)
        depth_qt_img = self._convert_image_to_pixmap(
            streamDepthFrame, self.display_width, self.display_height)
        self.window.cameraStreamLabel.setPixmap(color_qt_img)
        self.window.depthStreamLabel.setPixmap(depth_qt_img)

    @Slot(np.ndarray)
    def UpdateInfereceResultFrame(self, cameraStream):
        qt_img = self._convert_image_to_pixmap(
            cameraStream, self.display_width, self.display_height)
        if qt_img:
            self.window.debugResultLabel.setPixmap(qt_img)
        else:
            stream_size = (self.display_width, self.display_height)
            white_pixmap = QPixmap(stream_size).fill(Qt.GlobalColor.white)
            self.window.debugResultLabel.setPixmap(white_pixmap)

    @Slot(np.ndarray)
    def UpdateFaultInfereceResult(self, score):
        self._write_app_status("", "white", 30)
        self._write_debug_result_label("No object found with text prompt.", "blue", 25)

    def _convert_image_to_pixmap(self, cameraStream, stream_width, stream_height):
        """Convert from an opencv image to QPixmap"""
        rgb_image = cv2.cvtColor(cameraStream, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QtGui.QImage(
            rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format.Format_RGB888)
        p = convert_to_Qt_format.scaled(
            stream_width, stream_height, Qt.AspectRatioMode.KeepAspectRatio)
        # p = convert_to_Qt_format.scaled(stream_width, stream_height)
        return QPixmap.fromImage(p)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainwindow = MainWindow("mainwindow.ui")
    sys.exit(app.exec())
