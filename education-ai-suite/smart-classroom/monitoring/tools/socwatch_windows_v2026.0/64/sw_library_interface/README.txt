# ********************************************************************************
# INTEL CONFIDENTIAL
# Copyright 2020 Intel Corporation.

# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you (License). Unless the License provides otherwise, you may not
# use, modify, copy, publish, distribute, disclose or transmit this software or
# the related documents without Intel's prior written permission.

# This software and the related documents are provided as is, with no express
# or implied warranties, other than those that are expressly stated in the
# License.
# ********************************************************************************

README.txt

The SoCWatch INTERNAL & DCA packages contain the relevant files for supporting the SoCWatch library
interface usage. They are present in the 'sw_library_interface' directory in the SoCWatch package.
The 3 files of relevance are
    libSoCWatch.dll (Windows)/libSoCWatch.so (Linux)
    This is the SoCWatch interface library that needs to be linked by the user with their executable.

    socwatch_lib.h
    This file has all the available APIs to get a handle to the SoCWatch interface as well as
    configure, start and stop collections and details about the callback function that needs to be
    implemented by the SoCWatch interface user.

    socwatch_data.h
    This file contains data structures that SoCWatch uses to configure collection, populate data
    during collection (for continuous collections) that is received by the library user in the
    callback function.


Reference example code:
       An example usage of the SoCWatch library interface has been implemented in 'lib_example.cpp'
       present in the SoCWatch package. Please use it as a reference.
       The executables built from it are also part of the package, libSOCWatchExample.exe (Windows)
       and lib_example (Linux).
       Linux Run:
            - cd socwatch_chrome_linux_INTERNAL*
            - source ./setup_socwatch_env.sh
            - You can run './socwatch -h' to see what metrics are available
            - cd sw_library_interface
            - Run './lib_example -h' to check available options
            - Run './lib_example -f <metric_name> -t 5'
                - This will write to a file at end of collection AKA not continuous
            - Run './lib_example -f <metric_name> -t 5 --continuous'
                - This will dump data to the screen on the fly using the 'library_example.cpp'
                  example code callback method

        Windows Run:
            - cd socwatch_windows*\64
            - You can run 'socwatch.exe -h' to see what metrics are available
            - Copy 'sw_lib_interface\libSOCWatchExample.exe' and 'sw_library_interface\libSOCWatch.dll'
              to 'socwatch_windows*\64'
            - Run './libSOCWatchExample.exe -h' to check available options
            - Run './libSOCWatchExample.exe -f <metric_name> -t 5'
                - This will write to a file at end of collection AKA not continuous
            - Run './libSOCWatchExample.exe -f <metric_name> -t 5 --continuous'
                - This will dump data to the screen on the fly using the 'library_example.cpp'
                  example code callback method


Interface Documentation:
    SoCWatch library interface API and data structures documentation has been created using doxygen
    and is available in socwatch_lib_interface_doxygen.zip.

    Instructions:
        Unzip socwatch_lib_interface_doxygen.zip and start at socwatch_lib_doxygen/index.html

