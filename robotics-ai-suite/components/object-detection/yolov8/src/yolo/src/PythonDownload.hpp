// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0
//
// NOTE: This file contains functionality that downloads models from Ultralytics.
// Commercial use requires a commercial license from Ultralytics.
// See: https://ultralytics.com/license

#pragma once

#include <Python.h>

#include <filesystem>
#include <iostream>
#include <opencv2/core.hpp>
#include <sstream>
#include <string>
#include <unordered_map>

string download_model(
  cv::Size size, Task task, bool half = true, ModelSize model_size = ModelSize::N)
{
  string model_folder = "models";
  if (!filesystem::exists(model_folder)) {
    filesystem::create_directory(model_folder);
  }

  string base_name = "yolov8";
  string task_str = task_strs_strings[task];
  string model_size_string = model_size_strings[model_size];

  string half_string = half ? "True" : "False";

  string model_name = "yolov8" + model_size_string + task_str + ".pt";
  string model_final_name = base_name + model_size_string + task_str + "-" +
                            to_string(size.height) + "x" + to_string(size.width) + "-" +
                            half_string + ".onnx";

  if (filesystem::exists(model_folder + "/" + model_final_name)) {
    cout << "Using cached model" << endl;
    return model_folder + "/" + model_final_name;
  }

  static bool initialized = false;
  if (!initialized) {
    Py_Initialize();
    initialized = true;
  }
  std::string command =
    "from ultralytics import YOLO; \
    model = YOLO('" +
    model_name +
    "'); \
    model.export(format='onnx',imgsz=(" +
    to_string(size.height) + "," + to_string(size.width) + "),half=" + half_string +
    ",dynamic=False)";
  PyRun_SimpleString(command.c_str());

  string python_output_model_name = base_name + model_size_string + task_str + ".onnx";
  filesystem::rename(python_output_model_name, model_folder + "/" + model_final_name);

  return model_folder + "/" + model_final_name;
}
