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

import math
from typing import List
from threading import Lock
import cv2
import numpy as np

import rclpy
from cv_bridge import CvBridge, CvBridgeError

from rclpy.node import Node
from std_msgs.msg import Header
from sensor_msgs.msg import CameraInfo, Image
from image_geometry import PinholeCameraModel

from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

from transforms3d import quaternions

from rvc_messages.msg import PoseStamped, PoseStampedList
from rvc_vision_messages.msg import RotatedBB, RotatedBBList

from rvc_rotated_object_detection.rotated_object_detection_parameters import object_detection
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

class Object:
    def __init__(self, name, thickness, image_path, image_size, keypoints, descriptors):
        self._name = name
        self._thickness = thickness
        self._image_path = image_path
        self._image_size = image_size
        self._keypoints = keypoints
        self._descriptors = descriptors

    @property
    def name(self):
        return self._name

    @property
    def thickness(self):
        return self._thickness

    @property
    def image_path(self):
        return self._image_path

    @property
    def image_size(self):
        return self._image_size

    @property
    def keypoints(self):
        return self._keypoints

    @property
    def descriptors(self):
        return self._descriptors


class Detector:

    def __init__(self, orb_params, roi_params) -> None:
        self.orb_params = orb_params
        self.roi_params = roi_params
        self.orb = cv2.ORB_create(nfeatures=self.orb_params.nfeatures, nlevels=self.orb_params.nlevels,
                                  edgeThreshold=self.orb_params.edge_threshold, patchSize=self.orb_params.patch_size)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

        self.objects = {}

    def set_params(self, orb_params, roi_params):
        self.orb_params = orb_params
        self.roi_params = roi_params

    def initialize_object(self, obj_name, thickness, image_path, nfeatures):
        obj_image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if obj_image is None:
            raise ValueError(
                f"No image for object with name '{obj_name}' at path '{image_path}'")
        image_size = obj_image.shape[:2]
        self.orb.setMaxFeatures(nfeatures)
        keypoints, descriptors = self.orb.detectAndCompute(obj_image, None)
        self.orb.setMaxFeatures(self.orb_params.nfeatures)
        object = Object(obj_name, thickness, image_path,
                        image_size, keypoints, descriptors)
        self.objects[obj_name] = object

    def detect(self, img, header=None) -> tuple[RotatedBBList, List[np.array]]:

        img_size = img.shape[:2]
        img_cropped = img[self.roi_params.crop_top: img_size[0] - self.roi_params.crop_bottom,
                          self.roi_params.crop_left: img_size[1] - self.roi_params.crop_right]
        img_gray = cv2.cvtColor(img_cropped, cv2.COLOR_BGR2GRAY)
        img_keypoints, img_descriptors = self.orb.detectAndCompute(
            img_gray, None)

        detections = RotatedBBList()
        corners = []

        if img_descriptors is None:
            return detections, corners

        for obj in self.objects.values():
            matches = self.matcher.match(obj.descriptors, img_descriptors)

            if len(matches) > self.orb_params.min_matches:

                sorted_matches = sorted(matches, key=lambda x: x.distance)
                cropped_matches = sorted_matches[:self.orb_params.matches_limit]

                # extract the matched keypoints
                src_pts = np.float32(
                    [obj.keypoints[m.queryIdx].pt for m in cropped_matches]).reshape(-1, 1, 2)
                dst_pts = np.float32(
                    [img_keypoints[m.trainIdx].pt for m in cropped_matches]).reshape(-1, 1, 2)

                # find homography matrix
                M, mask = cv2.findHomography(
                    src_pts, dst_pts, cv2.RANSAC, self.orb_params.reproj_threshold)
                if M is None:
                    continue

                inliers = np.sum(mask)
                inliers_factor = inliers / len(mask)
                if inliers < self.orb_params.min_inliers or inliers_factor < self.orb_params.min_inliers_factor:
                    continue

                h, w = obj.image_size

                pts = np.float32(
                    [[0, 0], [0, h-1], [w-1, h-1], [w-1, 0]]).reshape(-1, 1, 2)
                dst = cv2.perspectiveTransform(pts, M)
                # reverse ROI cropping
                dst[:, :, 0] += self.roi_params.crop_left
                dst[:, :, 1] += self.roi_params.crop_top

                center = np.sum(dst, axis=0).squeeze() / 4

                if np.any(center < 0):
                    # center is outside of image
                    continue

                w_1 = dst[3, 0] - dst[0, 0]
                w_2 = dst[2, 0] - dst[1, 0]
                height = (np.linalg.norm(
                    dst[1, 0] - dst[0, 0]) + np.linalg.norm(dst[3, 0] - dst[2, 0])) / 2
                width = (np.linalg.norm(w_1) + np.linalg.norm(w_2)) / 2
                w_sum = w_1 + w_2
                theta_sum = np.arctan2(-w_sum[1], w_sum[0])

                if width < 0 or width > 65535 or height < 0 or height > 65535:
                    continue

                detection = RotatedBB()
                detection.header = header
                detection.object_id = obj.name
                detection.width = int(width)
                detection.height = int(height)

                detection.cx = int(center[0])
                detection.cy = int(center[1])
                detection.angle = float(theta_sum)

                detections.rotated_bb_list.append(detection)
                corners.append(dst)

        return detections, corners


class Projector:

    def __init__(self, projection_distance, objects):
        self.camera_model = None
        self.projection_distance = projection_distance
        self.objects = objects

    def project(self, header: Header, detections) -> PoseStampedList:
        poses = PoseStampedList()
        poses.header.frame_id = header.frame_id
        poses.header.stamp = header.stamp

        for detection in detections.rotated_bb_list:
            pose = PoseStamped()
            pose.pose_stamped.header = detection.header
            pose.last_observed = detection.header.stamp
            pose.obj_type = detection.object_id

            center = (detection.cx, detection.cy)
            ray = self.camera_model.projectPixelTo3dRay(
                self.camera_model.rectifyPoint(center))

            distance = self.projection_distance - \
                self.objects[detection.object_id].thickness / 2
            p_norm = np.array((0.0, 0.0, 1.0))
            r_dir = np.array(ray)
            t = distance / p_norm.dot(r_dir)

            center = r_dir * t
            pose.pose_stamped.pose.position.x = center[0]
            pose.pose_stamped.pose.position.y = center[1]
            pose.pose_stamped.pose.position.z = center[2]
            q = quaternions.axangle2quat((0.0, 0.0, -1.0), detection.angle)
            pose.pose_stamped.pose.orientation.w = q[0]
            pose.pose_stamped.pose.orientation.x = q[1]
            pose.pose_stamped.pose.orientation.y = q[2]
            pose.pose_stamped.pose.orientation.z = q[3]

            poses.poses.append(pose)

        return poses


def calculate_corners(rotated_bb: RotatedBB) -> np.array:
    corners = np.zeros((4, 2), dtype=np.int32)
    sin_rot = math.sin(rotated_bb.angle)
    cos_rot = math.cos(rotated_bb.angle)
    width_half = rotated_bb.width / 2
    height_half = rotated_bb.height / 2
    corners[0, 0] = rotated_bb.cx - cos_rot * \
        width_half - sin_rot * height_half
    corners[0, 1] = rotated_bb.cy + sin_rot * \
        width_half - cos_rot * height_half
    corners[1, 0] = rotated_bb.cx - cos_rot * \
        width_half + sin_rot * height_half
    corners[1, 1] = rotated_bb.cy + sin_rot * \
        width_half + cos_rot * height_half
    corners[2, 0] = rotated_bb.cx + cos_rot * \
        width_half + sin_rot * height_half
    corners[2, 1] = rotated_bb.cy - sin_rot * \
        width_half + cos_rot * height_half
    corners[3, 0] = rotated_bb.cx + cos_rot * \
        width_half - sin_rot * height_half
    corners[3, 1] = rotated_bb.cy - sin_rot * \
        width_half - cos_rot * height_half
    return corners


class ObjectDetection(Node):

    def __init__(self):
        super().__init__('object_detection')

        self.param_listener = object_detection.ParamListener(self)
        self.params = self.param_listener.get_params()

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        self.cam_subscription = self.create_subscription(
            Image, self.params.cam_prefix + '/' + self.params.cam_image_suffix, self.image_callback, qos)
        self.cam_subscription  # prevent unused variable warning
        self.cam_info_subscription = self.create_subscription(
            CameraInfo, self.params.cam_prefix + '/' + self.params.cam_info_suffix, self.camera_info_callback, qos)
        self.cam_info_subscription  # prevent unused variable warning

        self.detection_publisher = self.create_publisher(
            RotatedBBList, 'detections', 10)
        self.pose_publisher = self.create_publisher(
            PoseStampedList, 'object_poses', 10)
        self.image_publisher = self.create_publisher(
            Image, 'annotated_image', 10)

        self.cam_callback_lock = Lock()

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.detector = Detector(self.params.orb, self.params.roi)
        self.bridge = CvBridge()

        for obj_name in self.params.objects:
            obj = self.params.object.get_entry(obj_name)
            try:
                self.detector.initialize_object(
                    obj_name, obj.thickness, obj.image_path, obj.nfeatures)
            except Exception as ex:
                self.get_logger().warn(ex)

        self.projector = Projector(
            self.params.projection_distance, self.detector.objects)

    def image_callback(self, msg):
        self.get_logger().debug('Receiving image')
        if self.cam_callback_lock.locked():
            self.get_logger().debug('Processing previous frame, dropping')
            return

        with self.cam_callback_lock:
            if self.param_listener.is_old(self.params):
                self.params = self.param_listener.get_params()
                self.detector.set_params(self.params.orb, self.params.roi)

            try:
                cv_img = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            except CvBridgeError as e:
                self.get_logger().debug(e)
                return

            detections, corners = self.detector.detect(cv_img, msg.header)

            if self.params.publish_rotateBB_detection == True:
                self.detection_publisher.publish(detections)

            if self.params.annotate:
                image_annotated = cv_img.copy()
                image_size = image_annotated.shape[:2]
                roi_params = self.detector.roi_params
                roi = np.array([[roi_params.crop_left, roi_params.crop_top],
                                [roi_params.crop_left, image_size[0] -
                                    roi_params.crop_bottom],
                                [image_size[1] - roi_params.crop_right,
                                    image_size[0] - roi_params.crop_bottom],
                                [image_size[1] - roi_params.crop_right, roi_params.crop_top]],
                               np.int32)
                roi = roi.reshape((-1, 1, 2))
                image_annotated = cv2.polylines(
                    image_annotated, [roi], True, (0, 0, 255), 2, cv2.LINE_AA)
                for corner_array in corners:
                    image_annotated = cv2.polylines(image_annotated, [np.int32(
                        corner_array)], True, (255, 0, 0), 2, cv2.LINE_AA)
                for rotated_bb in detections.rotated_bb_list:
                    corners = calculate_corners(rotated_bb)
                    image_annotated = cv2.polylines(image_annotated, [np.int32(
                        corners.reshape(-1, 1, 2))], True, (0, 255, 0), 2, cv2.LINE_AA)
                    image_annotated = cv2.circle(
                        image_annotated, corners[0], radius=0, color=(0, 0, 255), thickness=2)
                self.image_publisher.publish(
                    self.bridge.cv2_to_imgmsg(image_annotated, encoding='bgr8'))

            if self.params.project:
                if self.projector.camera_model is None:
                    self.get_logger().info('Camera info not received and initialized')
                    return

                poses = self.projector.project(
                    msg.header, detections)
                if self.params.publish_object_poses == True:
                    self.pose_publisher.publish(poses)

    def camera_info_callback(self, info):
        self.get_logger().debug('Receiving camera info')
        self.camera_info = info
        if self.projector.camera_model is None:
            self.projector.camera_model = PinholeCameraModel()
        self.projector.camera_model.fromCameraInfo(info)


def main(args=None):
    rclpy.init(args=args)

    obj_detection = ObjectDetection()

    rclpy.spin(obj_detection)

    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    obj_detection.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
