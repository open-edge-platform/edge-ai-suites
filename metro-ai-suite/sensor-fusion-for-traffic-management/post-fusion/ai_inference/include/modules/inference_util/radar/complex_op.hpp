/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2021-2023 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and
 * your use of them is governed by the express license under which they were
 * provided to you (License). Unless the License provides otherwise, you may not
 * use, modify, copy, publish, distribute, disclose or transmit this software or
 * the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express
 * or implied warranties, other than those that are expressly stated in the
 * License.
 */

#pragma once

#include<math.h>
#include<stdio.h>
#include<stdlib.h>
#include<complex>

namespace hce{

namespace ai{

namespace inference{

using ComplexFloat = std::complex<float>;
using ComplexDouble = std::complex<double>;
static ComplexFloat operator/(ComplexFloat x, int c) {
    return ComplexFloat(x.real()/c, x.imag()/c);
}



template<typename T>
std::vector<float> linspace(T start_in, T end_in, int num_in)
{

  std::vector<float> linspaced;

  float start = static_cast<float>(start_in);
  float end = static_cast<float>(end_in);
  float num = static_cast<float>(num_in);

  if (num == 0) { return linspaced; }
  if (num == 1) 
    {
      linspaced.push_back(start);
      return linspaced;
    }

  float delta = (end - start) / (num - 1);

  for(int i=0; i < num-1; ++i)
    {
      linspaced.push_back(start + delta * i);
    }
  linspaced.push_back(end); // I want to ensure that start and end
                            // are exactly the same as the input
  return linspaced;
}

}   // namespace inference

}   // namespace ai

}   // namespace hce