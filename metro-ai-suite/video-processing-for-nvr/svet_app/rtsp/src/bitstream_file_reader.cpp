/*

 * INTEL CONFIDENTIAL

 *

 * Copyright (C) 2023-2024 Intel Corporation

 *

 * This software and the related documents are Intel copyrighted materials, and your use of them is governed by the

 * express license under which they were provided to you ("License"). Unless the License provides otherwise, you may not

 * use, modify, copy, publish, distribute, disclose or transmit this software or the related documents without Intel's

 * prior written permission.

 *

 * This software and the related documents are provided as is, with no express or implied warranties, other than those

 * that are expressly stated in the License.

 */

#include "bitstream_file_reader.h"
#include "spdlog/spdlog.h"

#include <string.h>
#include <assert.h>

using spdlog::debug;
using spdlog::error;
using spdlog::info;

BitstreamFileReader::BitstreamFileReader()
    :  mSource(nullptr) {
}

BitstreamFileReader::~BitstreamFileReader() {
    Close();
}

void BitstreamFileReader::Close() {
    if(mSource) {
        fclose(mSource);
	mSource = nullptr;
    }
}

void BitstreamFileReader::Reset() {
    if (!mInitialized)
        return;

    fseek(mSource, 0, SEEK_SET);
}

int BitstreamFileReader::Open(const char *fileName) {
    int sts = 0;
    assert (fileName != NULL);
    assert(strnlen(fileName, 256) != 0);

    //open file to read input stream
    mSource = fopen(fileName, "rb");
    if (!mSource)
    {
	error("SVET app: {0} Open {1} failed!", __func__, fileName);
        return -1;
    }
    mInitialized = true;

    return 0;
}

int BitstreamFileReader::Read(char *buffer, size_t bytesNum) {
    assert (buffer != NULL);
    return fread(buffer, 1, bytesNum, mSource); 
}

