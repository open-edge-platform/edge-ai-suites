# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

float32 confidence

uint32 x
uint32 y
uint32 height
uint32 width

string class_name

float32[] pose_xy #  X,Y of joints in image coordinates (17 total)
float32[] pose_visible # Probablity of joint being visible

float32[] mask
