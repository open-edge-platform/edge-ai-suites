// SPDX-License-Identifier: BSD-3-Clause
// SPDX-FileCopyrightText: (C) 2015 TRACLabs, Inc.
// Copyright 2021 Abrar Rahman Protyasha
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.


#ifndef TRAC_IK__VISIBILITY_CONTROL_HPP_
#define TRAC_IK__VISIBILITY_CONTROL_HPP_

// This logic was borrowed (then namespaced) from the examples on the gcc wiki:
//     https://gcc.gnu.org/wiki/Visibility

#if defined _WIN32 || defined __CYGWIN__
  #ifdef __GNUC__
    #define TRAC_IK_EXPORT __attribute__ ((dllexport))
    #define TRAC_IK_IMPORT __attribute__ ((dllimport))
  #else
    #define TRAC_IK_EXPORT __declspec(dllexport)
    #define TRAC_IK_IMPORT __declspec(dllimport)
  #endif
  #ifdef TRAC_IK_BUILDING_LIBRARY
    #define TRAC_IK_PUBLIC TRAC_IK_EXPORT
  #else
    #define TRAC_IK_PUBLIC TRAC_IK_IMPORT
  #endif
  #define TRAC_IK_PUBLIC_TYPE TRAC_IK_PUBLIC
  #define TRAC_IK_LOCAL
#else
  #define TRAC_IK_EXPORT __attribute__ ((visibility("default")))
  #define TRAC_IK_IMPORT
  #if __GNUC__ >= 4
    #define TRAC_IK_PUBLIC __attribute__ ((visibility("default")))
    #define TRAC_IK_LOCAL  __attribute__ ((visibility("hidden")))
  #else
    #define TRAC_IK_PUBLIC
    #define TRAC_IK_LOCAL
  #endif
  #define TRAC_IK_PUBLIC_TYPE
#endif

#endif  // TRAC_IK__VISIBILITY_CONTROL_HPP_
