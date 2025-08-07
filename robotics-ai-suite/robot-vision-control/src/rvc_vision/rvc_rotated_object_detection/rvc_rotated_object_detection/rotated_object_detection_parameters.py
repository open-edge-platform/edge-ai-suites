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

# auto-generated DO NOT EDIT

from rcl_interfaces.msg import ParameterDescriptor
from rcl_interfaces.msg import SetParametersResult
from rcl_interfaces.msg import FloatingPointRange, IntegerRange
from rclpy.clock import Clock
from rclpy.exceptions import InvalidParameterValueException
from rclpy.time import Time
import copy
import rclpy
from generate_parameter_library_py.python_validators import ParameterValidators



class object_detection:

    class Params:
        # for detecting if the parameter struct has been updated
        stamp_ = Time()

        cam_prefix = "/camera/color"
        cam_image_suffix = "image_raw"
        cam_info_suffix = "camera_info"
        log_level = "INFO"
        annotate = True
        publish_rotateBB_detection = True
        publish_object_poses = True
        objects = [""]
        project = True
        projection_distance = 0.5
        class __Roi:
            crop_top = 0
            crop_bottom = 0
            crop_left = 0
            crop_right = 0
        roi = __Roi()
        class __Orb:
            nfeatures = 500
            nlevels = 8
            edge_threshold = 5
            patch_size = 16
            reproj_threshold = 5.0
            min_matches = 20
            matches_limit = 20
            min_inliers = 10
            min_inliers_factor = 0.33
        orb = __Orb()
        class __Object:
            class __MapObjects:
                image_path = None
                nfeatures = 100
                thickness = 0.05
            __map_type = __MapObjects
            def add_entry(self, name):
                if not hasattr(self, name):
                    setattr(self, name, self.__map_type())
            def get_entry(self, name):
                return getattr(self, name)
        object = __Object()



    class ParamListener:
        def __init__(self, node, prefix=""):
            self.prefix_ = prefix
            self.params_ = object_detection.Params()
            self.node_ = node
            self.logger_ = rclpy.logging.get_logger("object_detection." + prefix)

            self.declare_params()

            self.node_.add_on_set_parameters_callback(self.update)
            self.clock_ = Clock()

        def get_params(self):
            tmp = self.params_.stamp_
            self.params_.stamp_ = None
            paramCopy = copy.deepcopy(self.params_)
            paramCopy.stamp_ = tmp
            self.params_.stamp_ = tmp
            return paramCopy

        def is_old(self, other_param):
            return self.params_.stamp_ != other_param.stamp_

        def refresh_dynamic_parameters(self):
            updated_params = self.get_params()
            # TODO remove any destroyed dynamic parameters

            # declare any new dynamic parameters
            for value in updated_params.objects:
                updated_params.object.add_entry(value)
                entry = updated_params.object.get_entry(value)
                param_name = f"{self.prefix_}object.{value}.image_path"
                if not self.node_.has_parameter(self.prefix_ + param_name):
                    descriptor = ParameterDescriptor(description="object image file path", read_only = True)
                    parameter = rclpy.Parameter.Type.STRING
                    self.node_.declare_parameter(param_name, parameter, descriptor)
                param = self.node_.get_parameter(param_name)
                self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
                entry.image_path = param.value
            for value in updated_params.objects:
                updated_params.object.add_entry(value)
                entry = updated_params.object.get_entry(value)
                param_name = f"{self.prefix_}object.{value}.nfeatures"
                if not self.node_.has_parameter(self.prefix_ + param_name):
                    descriptor = ParameterDescriptor(description="Maximum number of features", read_only = True)
                    parameter = entry.nfeatures
                    self.node_.declare_parameter(param_name, parameter, descriptor)
                param = self.node_.get_parameter(param_name)
                self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
                entry.nfeatures = param.value
            for value in updated_params.objects:
                updated_params.object.add_entry(value)
                entry = updated_params.object.get_entry(value)
                param_name = f"{self.prefix_}object.{value}.thickness"
                if not self.node_.has_parameter(self.prefix_ + param_name):
                    descriptor = ParameterDescriptor(description="object thickness / size parallel to optical axis", read_only = True)
                    parameter = entry.thickness
                    self.node_.declare_parameter(param_name, parameter, descriptor)
                param = self.node_.get_parameter(param_name)
                self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
                entry.thickness = param.value

        def update(self, parameters):
            updated_params = self.get_params()

            for param in parameters:
                if param.name == self.prefix_ + "cam_prefix":
                    updated_params.cam_prefix = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "cam_image_suffix":
                    updated_params.cam_image_suffix = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "cam_info_suffix":
                    updated_params.cam_info_suffix = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "log_level":
                    validation_result = ParameterValidators.one_of(param, ["DEBUG", "INFO", "WARN", "ERROR", "FATAL"])
                    if validation_result:
                        return SetParametersResult(successful=False, reason=validation_result)
                    updated_params.log_level = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "roi.crop_top":
                    updated_params.roi.crop_top = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "roi.crop_bottom":
                    updated_params.roi.crop_bottom = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "roi.crop_left":
                    updated_params.roi.crop_left = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "roi.crop_right":
                    updated_params.roi.crop_right = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "orb.nfeatures":
                    updated_params.orb.nfeatures = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "orb.nlevels":
                    updated_params.orb.nlevels = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "orb.edge_threshold":
                    updated_params.orb.edge_threshold = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "orb.patch_size":
                    updated_params.orb.patch_size = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "orb.reproj_threshold":
                    updated_params.orb.reproj_threshold = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "orb.min_matches":
                    validation_result = ParameterValidators.bounds(param, 10, 1000)
                    if validation_result:
                        return SetParametersResult(successful=False, reason=validation_result)
                    updated_params.orb.min_matches = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "orb.matches_limit":
                    validation_result = ParameterValidators.bounds(param, 10, 1000)
                    if validation_result:
                        return SetParametersResult(successful=False, reason=validation_result)
                    updated_params.orb.matches_limit = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "orb.min_inliers":
                    validation_result = ParameterValidators.bounds(param, 5, 50)
                    if validation_result:
                        return SetParametersResult(successful=False, reason=validation_result)
                    updated_params.orb.min_inliers = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "orb.min_inliers_factor":
                    validation_result = ParameterValidators.bounds(param, 0.0, 1.0)
                    if validation_result:
                        return SetParametersResult(successful=False, reason=validation_result)
                    updated_params.orb.min_inliers_factor = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "annotate":
                    updated_params.annotate = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "publish_rotateBB_detection":
                    updated_params.publish_rotateBB_detection = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "publish_object_poses":
                    updated_params.publish_object_poses = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "objects":
                    updated_params.objects = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "project":
                    updated_params.project = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                if param.name == self.prefix_ + "projection_distance":
                    updated_params.projection_distance = param.value
                    self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))


            # update dynamic parameters
            for param in parameters:
                for value in updated_params.objects:
                    param_name = f"{self.prefix_}object.{value}.image_path"
                    if param.name == param_name:
                        updated_params.object.objects_map[value].image_path = param.value
                        self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                for value in updated_params.objects:
                    param_name = f"{self.prefix_}object.{value}.nfeatures"
                    if param.name == param_name:
                        updated_params.object.objects_map[value].nfeatures = param.value
                        self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))

                for value in updated_params.objects:
                    param_name = f"{self.prefix_}object.{value}.thickness"
                    if param.name == param_name:
                        updated_params.object.objects_map[value].thickness = param.value
                        self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))


            updated_params.stamp_ = self.clock_.now()
            self.update_internal_params(updated_params)
            return SetParametersResult(successful=True)

        def update_internal_params(self, updated_params):
            self.params_ = updated_params

        def declare_params(self):
            updated_params = self.get_params()
            # declare all parameters and give default values to non-required ones
            if not self.node_.has_parameter(self.prefix_ + "cam_prefix"):
                descriptor = ParameterDescriptor(description="camera prefix", read_only = True)
                parameter = updated_params.cam_prefix
                self.node_.declare_parameter(self.prefix_ + "cam_prefix", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "cam_image_suffix"):
                descriptor = ParameterDescriptor(description="camera image topic suffix", read_only = True)
                parameter = updated_params.cam_image_suffix
                self.node_.declare_parameter(self.prefix_ + "cam_image_suffix", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "cam_info_suffix"):
                descriptor = ParameterDescriptor(description="camera info topic suffix", read_only = True)
                parameter = updated_params.cam_info_suffix
                self.node_.declare_parameter(self.prefix_ + "cam_info_suffix", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "log_level"):
                descriptor = ParameterDescriptor(description="debug log level [DEBUG|INFO|WARN|ERROR|FATAL]", read_only = True)
                parameter = updated_params.log_level
                self.node_.declare_parameter(self.prefix_ + "log_level", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "roi.crop_top"):
                descriptor = ParameterDescriptor(description="Pixels to crop top of the image", read_only = False)
                parameter = updated_params.roi.crop_top
                self.node_.declare_parameter(self.prefix_ + "roi.crop_top", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "roi.crop_bottom"):
                descriptor = ParameterDescriptor(description="Pixels to crop bottom of the image", read_only = False)
                parameter = updated_params.roi.crop_bottom
                self.node_.declare_parameter(self.prefix_ + "roi.crop_bottom", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "roi.crop_left"):
                descriptor = ParameterDescriptor(description="Pixels to crop left of the image", read_only = False)
                parameter = updated_params.roi.crop_left
                self.node_.declare_parameter(self.prefix_ + "roi.crop_left", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "roi.crop_right"):
                descriptor = ParameterDescriptor(description="Pixels to crop right of the image", read_only = False)
                parameter = updated_params.roi.crop_right
                self.node_.declare_parameter(self.prefix_ + "roi.crop_right", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "orb.nfeatures"):
                descriptor = ParameterDescriptor(description="Maximum number of features", read_only = True)
                parameter = updated_params.orb.nfeatures
                self.node_.declare_parameter(self.prefix_ + "orb.nfeatures", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "orb.nlevels"):
                descriptor = ParameterDescriptor(description="Number of pyramid features", read_only = True)
                parameter = updated_params.orb.nlevels
                self.node_.declare_parameter(self.prefix_ + "orb.nlevels", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "orb.edge_threshold"):
                descriptor = ParameterDescriptor(description="Size of the border where no features are detected", read_only = True)
                parameter = updated_params.orb.edge_threshold
                self.node_.declare_parameter(self.prefix_ + "orb.edge_threshold", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "orb.patch_size"):
                descriptor = ParameterDescriptor(description="Size of the patch", read_only = True)
                parameter = updated_params.orb.patch_size
                self.node_.declare_parameter(self.prefix_ + "orb.patch_size", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "orb.reproj_threshold"):
                descriptor = ParameterDescriptor(description="RANSAC reprojection threshold", read_only = False)
                parameter = updated_params.orb.reproj_threshold
                self.node_.declare_parameter(self.prefix_ + "orb.reproj_threshold", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "orb.min_matches"):
                descriptor = ParameterDescriptor(description="Minimum number of matches for detection", read_only = False)
                descriptor.integer_range.append(IntegerRange())
                descriptor.integer_range[-1].from_value = 10
                descriptor.integer_range[-1].to_value = 1000
                parameter = updated_params.orb.min_matches
                self.node_.declare_parameter(self.prefix_ + "orb.min_matches", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "orb.matches_limit"):
                descriptor = ParameterDescriptor(description="Number of matches limit for homography calculation", read_only = False)
                descriptor.integer_range.append(IntegerRange())
                descriptor.integer_range[-1].from_value = 10
                descriptor.integer_range[-1].to_value = 1000
                parameter = updated_params.orb.matches_limit
                self.node_.declare_parameter(self.prefix_ + "orb.matches_limit", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "orb.min_inliers"):
                descriptor = ParameterDescriptor(description="Minimum number of inliers for homography calculation", read_only = False)
                descriptor.integer_range.append(IntegerRange())
                descriptor.integer_range[-1].from_value = 5
                descriptor.integer_range[-1].to_value = 50
                parameter = updated_params.orb.min_inliers
                self.node_.declare_parameter(self.prefix_ + "orb.min_inliers", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "orb.min_inliers_factor"):
                descriptor = ParameterDescriptor(description="Minimum factor of inliers vs all matches for homography calculation", read_only = False)
                descriptor.floating_point_range.append(FloatingPointRange())
                descriptor.floating_point_range[-1].from_value = 0.0
                descriptor.floating_point_range[-1].to_value = 1.0
                parameter = updated_params.orb.min_inliers_factor
                self.node_.declare_parameter(self.prefix_ + "orb.min_inliers_factor", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "annotate"):
                descriptor = ParameterDescriptor(description="provide annotated images output", read_only = True)
                parameter = updated_params.annotate
                self.node_.declare_parameter(self.prefix_ + "annotate", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "publish_rotateBB_detection"):
                descriptor = ParameterDescriptor(description="publish rotated BB detection output", read_only = True)
                parameter = updated_params.publish_rotateBB_detection
                self.node_.declare_parameter(self.prefix_ + "publish_rotateBB_detection", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "publish_object_poses"):
                descriptor = ParameterDescriptor(description="publish object_poses rvc_messages API message output", read_only = True)
                parameter = updated_params.publish_object_poses
                self.node_.declare_parameter(self.prefix_ + "publish_object_poses", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "objects"):
                descriptor = ParameterDescriptor(description="list of object names for detection", read_only = True)
                parameter = updated_params.objects
                self.node_.declare_parameter(self.prefix_ + "objects", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "project"):
                descriptor = ParameterDescriptor(description="project objects onto plane", read_only = True)
                parameter = updated_params.project
                self.node_.declare_parameter(self.prefix_ + "project", parameter, descriptor)

            if not self.node_.has_parameter(self.prefix_ + "projection_distance"):
                descriptor = ParameterDescriptor(description="distance from camera to projection plane", read_only = True)
                parameter = updated_params.projection_distance
                self.node_.declare_parameter(self.prefix_ + "projection_distance", parameter, descriptor)

            # TODO: need validation
            # get parameters and fill struct fields
            param = self.node_.get_parameter(self.prefix_ + "cam_prefix")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.cam_prefix = param.value
            param = self.node_.get_parameter(self.prefix_ + "cam_image_suffix")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.cam_image_suffix = param.value
            param = self.node_.get_parameter(self.prefix_ + "cam_info_suffix")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.cam_info_suffix = param.value
            param = self.node_.get_parameter(self.prefix_ + "log_level")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            validation_result = ParameterValidators.one_of(param, ["DEBUG", "INFO", "WARN", "ERROR", "FATAL"])
            if validation_result:
                raise InvalidParameterValueException('log_level',param.value, 'Invalid value set during initialization for parameter log_level: ' + validation_result)
            updated_params.log_level = param.value
            param = self.node_.get_parameter(self.prefix_ + "roi.crop_top")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.roi.crop_top = param.value
            param = self.node_.get_parameter(self.prefix_ + "roi.crop_bottom")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.roi.crop_bottom = param.value
            param = self.node_.get_parameter(self.prefix_ + "roi.crop_left")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.roi.crop_left = param.value
            param = self.node_.get_parameter(self.prefix_ + "roi.crop_right")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.roi.crop_right = param.value
            param = self.node_.get_parameter(self.prefix_ + "orb.nfeatures")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.orb.nfeatures = param.value
            param = self.node_.get_parameter(self.prefix_ + "orb.nlevels")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.orb.nlevels = param.value
            param = self.node_.get_parameter(self.prefix_ + "orb.edge_threshold")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.orb.edge_threshold = param.value
            param = self.node_.get_parameter(self.prefix_ + "orb.patch_size")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.orb.patch_size = param.value
            param = self.node_.get_parameter(self.prefix_ + "orb.reproj_threshold")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.orb.reproj_threshold = param.value
            param = self.node_.get_parameter(self.prefix_ + "orb.min_matches")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            validation_result = ParameterValidators.bounds(param, 10, 1000)
            if validation_result:
                raise InvalidParameterValueException('orb.min_matches',param.value, 'Invalid value set during initialization for parameter orb.min_matches: ' + validation_result)
            updated_params.orb.min_matches = param.value
            param = self.node_.get_parameter(self.prefix_ + "orb.matches_limit")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            validation_result = ParameterValidators.bounds(param, 10, 1000)
            if validation_result:
                raise InvalidParameterValueException('orb.matches_limit',param.value, 'Invalid value set during initialization for parameter orb.matches_limit: ' + validation_result)
            updated_params.orb.matches_limit = param.value
            param = self.node_.get_parameter(self.prefix_ + "orb.min_inliers")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            validation_result = ParameterValidators.bounds(param, 5, 50)
            if validation_result:
                raise InvalidParameterValueException('orb.min_inliers',param.value, 'Invalid value set during initialization for parameter orb.min_inliers: ' + validation_result)
            updated_params.orb.min_inliers = param.value
            param = self.node_.get_parameter(self.prefix_ + "orb.min_inliers_factor")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            validation_result = ParameterValidators.bounds(param, 0.0, 1.0)
            if validation_result:
                raise InvalidParameterValueException('orb.min_inliers_factor',param.value, 'Invalid value set during initialization for parameter orb.min_inliers_factor: ' + validation_result)
            updated_params.orb.min_inliers_factor = param.value
            param = self.node_.get_parameter(self.prefix_ + "annotate")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.annotate = param.value
            param = self.node_.get_parameter(self.prefix_ + "publish_rotateBB_detection")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.publish_rotateBB_detection = param.value
            param = self.node_.get_parameter(self.prefix_ + "publish_object_poses")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.publish_object_poses = param.value
            param = self.node_.get_parameter(self.prefix_ + "objects")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.objects = param.value
            param = self.node_.get_parameter(self.prefix_ + "project")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.project = param.value
            param = self.node_.get_parameter(self.prefix_ + "projection_distance")
            self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
            updated_params.projection_distance = param.value


            # declare and set all dynamic parameters
            for value in updated_params.objects:
                updated_params.object.add_entry(value)
                entry = updated_params.object.get_entry(value)
                param_name = f"{self.prefix_}object.{value}.image_path"
                if not self.node_.has_parameter(self.prefix_ + param_name):
                    descriptor = ParameterDescriptor(description="object image file path", read_only = True)
                    parameter = rclpy.Parameter.Type.STRING
                    self.node_.declare_parameter(param_name, parameter, descriptor)
                param = self.node_.get_parameter(param_name)
                self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
                entry.image_path = param.value
            for value in updated_params.objects:
                updated_params.object.add_entry(value)
                entry = updated_params.object.get_entry(value)
                param_name = f"{self.prefix_}object.{value}.nfeatures"
                if not self.node_.has_parameter(self.prefix_ + param_name):
                    descriptor = ParameterDescriptor(description="Maximum number of features", read_only = True)
                    parameter = entry.nfeatures
                    self.node_.declare_parameter(param_name, parameter, descriptor)
                param = self.node_.get_parameter(param_name)
                self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
                entry.nfeatures = param.value
            for value in updated_params.objects:
                updated_params.object.add_entry(value)
                entry = updated_params.object.get_entry(value)
                param_name = f"{self.prefix_}object.{value}.thickness"
                if not self.node_.has_parameter(self.prefix_ + param_name):
                    descriptor = ParameterDescriptor(description="object thickness / size parallel to optical axis", read_only = True)
                    parameter = entry.thickness
                    self.node_.declare_parameter(param_name, parameter, descriptor)
                param = self.node_.get_parameter(param_name)
                self.logger_.debug(param.name + ": " + param.type_.name + " = " + str(param.value))
                entry.thickness = param.value

            self.update_internal_params(updated_params)
