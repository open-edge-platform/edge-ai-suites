# INTEL CONFIDENTIAL
#
# Copyright (C) 2021-2022 Intel Corporation.
#
# This software and the related documents are Intel copyrighted materials, and your use of
# them is governed by the express license under which they were provided to you (License).
# Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
# disclose or transmit this software or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or implied warranties,
# other than those that are expressly stated in the License.

find_library (HDDLUNITE_LIB NAMES HddlUnite HINTS ENV LD_LIBRARY_PATH)

get_filename_component(HDDLUNITE_INCLUDE_DIR_HINT ${HDDLUNITE_LIB} DIRECTORY)

find_path(HDDLUNITE_INCLUDE_DIR NAMES WorkloadContext.h HINTS "${HDDLUNITE_INCLUDE_DIR_HINT}/../include")

message ("HddlUnite header directory: ${HDDLUNITE_INCLUDE_DIR}")
message ("HddlUnite lib: ${HDDLUNITE_LIB}")