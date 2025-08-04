// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <gtest/gtest.h>
#include <iostream>

int main(int argc, char ** argv)
{
  try
  {
    ::testing::InitGoogleTest(&argc, argv);
  }
  catch(...)
  {
    std::cerr << "Failed to initialize gtest" << std::endl;
  }
  //::testing::InitGoogleTest(&argc, argv);
  bool all_successful;
  try
  {
    all_successful = RUN_ALL_TESTS();
  }
  catch(...)
  {
    std::cerr << "RUN_ALL_TESTS threw an exception" << std::endl;
  }
  return all_successful;
}