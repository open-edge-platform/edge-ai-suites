/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2023-2024 Intel Corporation
 *
 * This software and the related documents are Intel copyrighted materials, and your use of them is governed by the
 * express license under which they were provided to you ("License"). Unless the License provides otherwise, you may not
 * use, modify, copy, publish, distribute, disclose or transmit this software or the related documents without Intel's
 * prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties, other than those
 * that are expressly stated in the License.
 */

#include "vpp_common.h"
#include "vpp_encode.h"
#include "vpp_osd.h"
#include "vpp_decode.h"
#include "vpp_system.h"
#include "vpp_display.h"
#include "vpp_postprocessing.h"
#include <thread>
#include <iostream>
#include <unistd.h>
#include <cassert>

#include <vector>
#include <memory>
#include <chrono>
#include <cstring>
#include <fstream>
#include <atomic>
#include <cstdlib>

#include "bitstream_file_reader.h"
#include "bitstream_rtsp_reader.h"
#include "CLI/CLI.hpp"
using CLI::enums::operator<<;

// ===========================================================================
// H.264/H.265 NALU type judgment
// ===========================================================================
enum NaluType {
    NALU_UNKNOWN = 0,
    NALU_I_FRAME,   // iframe (IDR/CRA/Bla...)
    NALU_CONFIG,    // config frame (SPS/PPS/VPS)
    NALU_P_B_FRAME  // p/b frame
};

// search startcode "00 00 01" or "00 00 00 01"
static const uint8_t* FindStartCode(const uint8_t* p, const uint8_t* end) {
    for (const uint8_t* ptr = p; ptr < end - 3; ++ptr) {
        if (ptr[0] == 0x00 && ptr[1] == 0x00) {
            if (ptr[2] == 0x01) return ptr + 3; // Found 00 00 01
            if (ptr[2] == 0x00 && ptr[3] == 0x01) return ptr + 4; // Found 00 00 00 01
        }
    }
    return nullptr;
}

// check what's in buffer
// return: if buffer is going to decode
// keepState: keep if it is reading iframe now
// Strict filtering logic: IDR is turned on first, P frame is turned off first
static bool CheckBufferKeepStrict(const uint8_t* data, size_t size, VPP_CODEC_STANDARD codec, bool& keepState) {
    if (size < 5) return keepState;

    const uint8_t* ptr = data;
    const uint8_t* end = data + size;
    bool foundIDR = false;
    bool foundP = false;
    bool foundConfig = false;

    while (ptr < end - 4) {
        uint32_t startCodeLen = 0;
        if (ptr[0] == 0x00 && ptr[1] == 0x00) {
            if (ptr[2] == 0x01) startCodeLen = 3;
            else if (ptr[2] == 0x00 && ptr[3] == 0x01) startCodeLen = 4;
        }
        if (startCodeLen > 0) {
            uint8_t header = ptr[startCodeLen];
            int nalu_type = -1;
            if (codec == VPP_CODEC_STANDARD_H264) {
                nalu_type = header & 0x1F;
                if (nalu_type == 7 || nalu_type == 8) foundConfig = true;
                else if (nalu_type == 5) { foundIDR = true; keepState = true; }
                else if (nalu_type == 1) { foundP = true; keepState = false; }
            } else if (codec == VPP_CODEC_STANDARD_H265) {
                nalu_type = (header & 0x7E) >> 1;
                if (nalu_type >= 32 && nalu_type <= 34) foundConfig = true;
                else if (nalu_type >= 16 && nalu_type <= 21) { foundIDR = true; keepState = true; }
                else if (nalu_type <= 15) { foundP = true; keepState = false; }
            }
            ptr += startCodeLen + 1;
        } else { ptr++; }
    }

    // Core priority determination:
    if (foundIDR) return true;   // 1. As long as there is an I frame, it must pass
    if (foundP)   return false;  // 2. If there is no I frame but there is a P frame, it must be blocked (even if there is PPS)
    if (foundConfig) return true; // 3. Pure configuration package, allowed (used to initialize the decoder)
    return keepState;            // 4. Fragmented data, following gate status
}

// change mapped NV12 (surf.Y + surf.UV) into YU12 (Y + U + V)
// size of yu12Buf is at least w*h*3/2, layout: [Y(wh)] [U(wh/4)] [V(wh/4)]
static inline void NV12SurfToYU12(const VPP_SURFACE& surf, uint8_t* yu12Buf, bool uvIsVU=false) {
    const int W = int(surf.Width)  - int(surf.CropLeft) - int(surf.CropRight);
    const int H = int(surf.Height) - int(surf.CropTop)  - int(surf.CropBottom);

    const int yStride  = surf.Pitches[0];
    const int uvStride = surf.Pitches[1] ? surf.Pitches[1] : surf.Pitches[0];

    // Y: 用原始 crop（精确 ROI）
    const uint8_t* srcY = surf.Y + surf.CropTop * yStride + surf.CropLeft;

    // UV: 强制偶数对齐（关键！）
    const int cropXuv = (surf.CropLeft & ~1);
    const int cropYuv = (surf.CropTop  & ~1);
    const uint8_t* srcUV = surf.UV + (cropYuv / 2) * uvStride + cropXuv;

    uint8_t* dstY = yu12Buf;
    uint8_t* dstU = yu12Buf + W * H;
    uint8_t* dstV = dstU + (W * H) / 4;

    // copy Y
    for (int r = 0; r < H; ++r) {
        memcpy(dstY + r * W, srcY + r * yStride, W);
    }

    // split UV -> U/V
    for (int r = 0; r < H / 2; ++r) {
        const uint8_t* p = srcUV + r * uvStride;
        uint8_t* u = dstU + r * (W / 2);
        uint8_t* v = dstV + r * (W / 2);
        for (int c = 0; c < W / 2; ++c) {
            uint8_t a = p[c * 2 + 0];
            uint8_t b = p[c * 2 + 1];
            if (!uvIsVU) {   // NV12: U,V
                u[c] = a; v[c] = b;
            } else {          // NV21: V,U
                u[c] = b; v[c] = a;
            }
        }
    }
}

// wrapped out mapped NV12 surface to NV12 file
// output layout: Y( W*H ) + UV( W*H/2 )，can use "ffplay -pixel_format nv12" to test
static inline bool DumpNV12ToFile_Tight(const VPP_SURFACE& surf, const std::string& path) {
    // 1) ROI size
    const int W = int(surf.Width)  - int(surf.CropLeft) - int(surf.CropRight);
    const int H = int(surf.Height) - int(surf.CropTop)  - int(surf.CropBottom);
    if (W <= 0 || H <= 0) return false;

    // NV12（4:2:0）
    // if ((W & 1) || (H & 1)) return false;

    // 2) stride
    const int yStride  = surf.Pitches[0];
    const int uvStride = surf.Pitches[1] ? surf.Pitches[1] : surf.Pitches[0];

    // 3) 
    const int cropX_Y  = surf.CropLeft;
    const int cropY_Y  = surf.CropTop;
    const int cropX_UV = surf.CropLeft & ~1; 
    const int cropY_UV = surf.CropTop  & ~1; 

    const uint8_t* srcY  = surf.Y  + cropY_Y  * yStride  + cropX_Y;
    const uint8_t* srcUV = surf.UV + (cropY_UV / 2) * uvStride + cropX_UV;

    // 4) package into buffer
    std::vector<uint8_t> nv12(W * H * 3 / 2);
    uint8_t* dstY  = nv12.data();
    uint8_t* dstUV = nv12.data() + (W * H);

    // copy Y
    for (int r = 0; r < H; ++r) {
        memcpy(dstY + r * W, srcY + r * yStride, W);
    }
    // copy UV
    for (int r = 0; r < H / 2; ++r) {
        memcpy(dstUV + r * W, srcUV + r * uvStride, W);
    }

    FILE* f = fopen(path.c_str(), "wb");
    if (!f) return false;
    fwrite(nv12.data(), 1, nv12.size(), f);
    fclose(f);
    return true;
}

static inline void PackNV12_Tight(const VPP_SURFACE& surf, std::vector<uint8_t>& outNv12) {
    const int W = int(surf.Width)  - int(surf.CropLeft) - int(surf.CropRight);
    const int H = int(surf.Height) - int(surf.CropTop)  - int(surf.CropBottom);
    const int yStride  = surf.Pitches[0];
    const int uvStride = surf.Pitches[1] ? surf.Pitches[1] : surf.Pitches[0];

    const uint8_t* srcY  = surf.Y  + surf.CropTop * yStride + surf.CropLeft;
    const uint8_t* srcUV = surf.UV + (surf.CropTop/2) * uvStride + surf.CropLeft;

    outNv12.resize(W * H * 3 / 2);
    uint8_t* dstY  = outNv12.data();
    uint8_t* dstUV = outNv12.data() + W * H;

    for (int r = 0; r < H; ++r) memcpy(dstY  + r * W, srcY  + r * yStride,  W);
    for (int r = 0; r < H/2; ++r) memcpy(dstUV + r * W, srcUV + r * uvStride, W);
}

static inline void YU12_To_NV12_Tight(const uint8_t* yu12, int W, int H, std::vector<uint8_t>& outNv12) {
    const uint8_t* srcY = yu12;
    const uint8_t* srcU = yu12 + W * H;
    const uint8_t* srcV = srcU + (W * H) / 4;

    outNv12.resize(W * H * 3 / 2);
    uint8_t* dstY  = outNv12.data();
    uint8_t* dstUV = outNv12.data() + W * H;

    // Y
    memcpy(dstY, srcY, W * H);

    // UV interleave
    for (int r = 0; r < H/2; ++r) {
        uint8_t* uv = dstUV + r * W;
        const uint8_t* u = srcU + r * (W/2);
        const uint8_t* v = srcV + r * (W/2);
        for (int c = 0; c < W/2; ++c) {
            uv[2*c + 0] = u[c];
            uv[2*c + 1] = v[c];
        }
    }
}

#define FILENAME_MAXCHAR 128
#define FEED_DECODE_MIN_SIZE 64
#define read
#define DECODE_ENABLE
// #define mapsurface
// #define yu12test
const unsigned int SENDINPUT_INTERVAL = 20*10;
const unsigned int SENDINPUT_RETRY = 20;
static const int mBufSize = 1024*1024;

int main(int argc, char **argv)
{
    CLI::App app{"App description"};
    
    int STREAM_NUM = 64;
    int running_time = 60;
    int skip_frame = 1000;
    bool write_file = true;
    uint32_t quality = 100;
    // VPP_CODEC_STANDARD codec = VPP_CODEC_STANDARD_H265;
    VPP_CODEC_STANDARD codec = VPP_CODEC_STANDARD_H264;
    std::string input_file = {"config.txt"};
    std::string output_profix = {"img_"};
    std::string input_mode = {"rtsp"};
    bool iframe_on = false;

    // Define options
    app.add_option("--stream-number,-n", STREAM_NUM, "Stream number (>=0, <100)")->capture_default_str();
    app.add_option("--time,-t", running_time, "Running time(seconds) of this program (>=1)")->capture_default_str();
    app.add_option("--skip-frame,-s", skip_frame, "Skip frames (>=0)")->capture_default_str();
    app.add_option("--write-file,-w", write_file, "Diong encoding and Write down jpg files (true or false)")->capture_default_str();
    app.add_option("--quality,-q", quality, "Encode jpeg quality (<=100)")->capture_default_str();
    app.add_option("--codec,-c", codec, "Codec standard (h265/h264)")->capture_default_str();
    app.add_option("--input-file,-f", input_file, "Path of url config file in rtsp mode, or input file in file mode")->capture_default_str();
    app.add_option("--output-profix,-o", output_profix, "Profix of output file name")->capture_default_str();
    app.add_option("--mode,-m", input_mode, "Input mode of video streams(rtsp or file)")->capture_default_str();
    app.add_option("--iframe-on,-i", iframe_on, "Only decoding and encoding iframes(true of false)")->capture_default_str();
    /*
     *  RTSP mode supports only i-frame decoding and encoding by identifying nal_unit_type
     *  File mode currently does not support the function of decoding and encoding only i frames.
     */
    CLI11_PARSE(app, argc, argv);

    std::cout << "skip_frame = " << skip_frame << "\n";
    std::cout << "codec = " << codec << "\n";

    //surface pool + encode(JPEG)
    VPP_Init();
    
    std::vector<std::string> urls;
    if(input_mode == "rtsp") {
        // Read urls from config file (vector<string>)
        std::ifstream ifs(input_file);
        if (!ifs.is_open()) return -1;
        urls.reserve(STREAM_NUM);
        std::string line;
        while ((int)urls.size() < STREAM_NUM && std::getline(ifs, line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (!line.empty()) urls.push_back(line);
        }
        ifs.close();
        if ((int)urls.size() < STREAM_NUM) {
            std::cout << "Only " << urls.size() << " urls in config, reduce STREAM_NUM\n";
            STREAM_NUM = (int)urls.size();
        }
    }

    std::vector<std::shared_ptr<BitstreamReader>> readers(STREAM_NUM);
    std::vector<std::vector<uint8_t>> bufs(STREAM_NUM, std::vector<uint8_t>(mBufSize));
    std::atomic<bool> flagFeed{true};// flagGlobal 1
    std::atomic<bool> flagProc{true};// flagGlobal 2

    auto workload_feed = [&](int32_t stream_id) {
        int32_t decode_id = stream_id;
        bool isFeeding = false; // true if IDR
        auto &mBuf = bufs[stream_id];
        auto reader = readers[stream_id]; // local copy of shared_ptr
        
        while (flagFeed.load(std::memory_order_relaxed)) {
            #ifdef read
            // Read + FeedInput
            int retBytes = reader->Read((char*)mBuf.data(), mBufSize);
            
            if (retBytes <= 0) {
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
                continue;
            }
            // Read until size comes to MIN SIZE
            if (retBytes > 0 && retBytes < FEED_DECODE_MIN_SIZE) {
                for (int k = 0; k < 10; k++) {
                    char* ptr = (char*)mBuf.data() + retBytes;
                    int bytes = reader->Read(ptr, mBufSize - retBytes);
                    if (bytes > 0) {
                        retBytes += bytes;
                        // printf("Read() success. ");
                        if (bytes < FEED_DECODE_MIN_SIZE) continue;
                        break;
                    } else {
                        printf("Read() failed. ");
                        break;
                    }
                }
            }
            #endif 
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            // if (!flagFeed.load(std::memory_order_relaxed)) 
            // {
            //     std::cout << "breaking!!!" << std::endl;
            //     break;
            // }
            
            #ifdef DECODE_ENABLE
            // after Reading
            bool shouldFeed = true;
            if(iframe_on) {
                shouldFeed = CheckBufferKeepStrict(mBuf.data(), retBytes, codec, isFeeding);
            }
            if (shouldFeed) {
                VPP_DECODE_STREAM_InputBuffer buffer{};
                buffer.pAddr = mBuf.data();
                buffer.BasePts = 0;
                buffer.FlagEOStream = false;
                buffer.FlagEOFrame = false;
                buffer.Length = retBytes;
                
                // VPP_STATUS feedSts = VPP_DECODE_STREAM_FeedInput(decode_id, &buffer, -1);
                VPP_STATUS feedSts = VPP_DECODE_STREAM_FeedInput(decode_id, &buffer, 5000);
                
                unsigned int rcnt = 0;
                while (feedSts == VPP_STATUS_ERR_DECODE_RINGBUFFER_FULL && rcnt++ < SENDINPUT_RETRY) {
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                    // feedSts = VPP_DECODE_STREAM_FeedInput(decode_id, &buffer, -1);
                    feedSts = VPP_DECODE_STREAM_FeedInput(decode_id, &buffer, 5000);
                }
                if (feedSts != VPP_STATUS_SUCCESS) {
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                    // continue;
                    break;
                }
            }
            // Feed or SKIP
            // printf("Stream %d: Size=%d, isFeedingState=%d, Action=%s\n", 
            //        stream_id, retBytes, isFeeding, shouldFeed ? "FEED" : "SKIP");
            #endif
        }
        // std::cout << "[close] i=" << stream_id << " use_count=" << readers[stream_id].use_count() << std::endl;
        // if (reader) reader->Close();

        // std::this_thread::sleep_for(std::chrono::milliseconds(1000));
        // readers[stream_id].reset();

    };

    auto workload_feed_file = [&](int32_t stream_id) {
        int32_t decode_id = stream_id;
        bool isFeeding = false; 
        auto &mBuf = bufs[stream_id];

        FILE* fp = fopen(input_file.c_str(), "rb");
        if (!fp) {
            std::cerr << "[file] open failed: " << input_file << " stream=" << stream_id << "\n";
            return;
        }

        while (flagFeed.load(std::memory_order_relaxed)) {
            size_t n = fread(mBuf.data(), 1, mBuf.size(), fp);
            if (!flagFeed.load(std::memory_order_relaxed)) break;
            
            if (n == 0) {
                // EOF or error: rewind and continue
                clearerr(fp);
                fseek(fp, 0, SEEK_SET);
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
                continue;
            }
            
            if (n < mBuf.size()) {
                clearerr(fp);
                fseek(fp, 0, SEEK_SET);
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
                
            }
            
    #ifdef DECODE_ENABLE
            VPP_DECODE_STREAM_InputBuffer buffer{};
            buffer.pAddr = (uint8_t*)mBuf.data();
            buffer.Length = (uint32_t)n;
            buffer.BasePts = 0;
            buffer.FlagEOStream = false;
            buffer.FlagEOFrame = false;
            
            // VPP_STATUS feedSts = VPP_DECODE_STREAM_FeedInput(decode_id, &buffer, -1);
            VPP_STATUS feedSts = VPP_DECODE_STREAM_FeedInput(decode_id, &buffer, 5000);
            unsigned int rcnt = 0;
            while (feedSts == VPP_STATUS_ERR_DECODE_RINGBUFFER_FULL && rcnt++ < SENDINPUT_RETRY) {
                std::cout << "RETRY " << rcnt;
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
                // feedSts = VPP_DECODE_STREAM_FeedInput(decode_id, &buffer, -1);
                feedSts = VPP_DECODE_STREAM_FeedInput(decode_id, &buffer, 5000);
            }
            if (feedSts != VPP_STATUS_SUCCESS) {
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
                continue;
            }
    #else
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
    #endif
        }

        fclose(fp);
    };


    auto workload_proc = [&](int32_t stream_id) {            
        int32_t encode_id = stream_id;
        int32_t decode_id = stream_id;
        
        #ifdef mapsurface
        int frame_idx = 0;        
        // YU12 buffer sizes
        const int D1_W = 720;
        const int D1_H = 480;
        std::vector<uint8_t> yu12Buf(D1_W * D1_H * 3 / 2);
        #endif

        size_t i = 0;
        while (flagProc.load(std::memory_order_relaxed)) {
            #ifdef DECODE_ENABLE
            VPP_SURFACE_HDL hdl;
            VPP_STATUS sts = VPP_DECODE_STREAM_GetFrame(decode_id, &hdl, 5000);
            // VPP_STATUS sts = VPP_DECODE_STREAM_GetFrame(decode_id, &hdl, 200);
            if (sts == VPP_STATUS_SUCCESS) {
                VPP_SURFACE surf{};
                sts = VPP_SYS_MapSurface(hdl, &surf); // Must be mapped first
                if (sts == VPP_STATUS_SUCCESS) {
                    // Print PTS. TimeStamp is usually uint64_t, use %llu to force printing
                    // printf("[DEBUG] Stream %d: Decoded Frame PTS = %llu\n", 
                        // stream_id, (unsigned long long)surf.TimeStamp);
                        }
                VPP_SYS_UnmapSurface(hdl, &surf); // Unmap
            }
            if (sts != VPP_STATUS_SUCCESS) {
                // if no frame, continue
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
                continue;
            }
            #endif

            #ifdef mapsurface
            if(frame_idx % 3 == 0) {
                VPP_SURFACE surf{};
                sts = VPP_SYS_MapSurface(hdl, &surf);
                #ifdef yu12test
                int W = surf.Width - surf.CropLeft - surf.CropRight;
                int H = surf.Height - surf.CropTop  - surf.CropBottom;
                printf("ROI=%dx%d Crop(L,T,R,B)=(%u,%u,%u,%u) Pitch(Y,UV)=(%u,%u)\n",
                    W,H, surf.CropLeft, surf.CropTop, surf.CropRight, surf.CropBottom,
                    surf.Pitches[0], surf.Pitches[1]);
                #endif
                if (sts == VPP_STATUS_SUCCESS) {
                    if(surf.PixelFormat != VPP_PIXEL_FORMAT_NV12) break;
                    const int w = int(surf.Width)  - int(surf.CropLeft) - int(surf.CropRight);
                    const int h = int(surf.Height) - int(surf.CropTop)  - int(surf.CropBottom);

                    if (w == D1_W && h == D1_H) {
                        NV12SurfToYU12(surf, yu12Buf.data(), false);
                    }
                    #ifdef yu12test
                    if (frame_idx == 180) {
                        DumpNV12ToFile_Tight(surf, "./out_720x480_nv12.yuv");
                        FILE* f = fopen("./out_720x480_yu12.yuv", "wb");
                        fwrite(yu12Buf.data(), 1, D1_W*D1_H*3/2, f);
                        fclose(f);

                        const int W = 720, H = 480;
                        // 1) src tight NV12（from mapped surface）
                        std::vector<uint8_t> nv12_src;
                        PackNV12_Tight(surf, nv12_src);
                        // 2) NV12->YU12
                        std::vector<uint8_t> yu12(W * H * 3 / 2);
                        NV12SurfToYU12(surf, yu12.data()); 
                        // 3) YU12 -> tight NV12
                        std::vector<uint8_t> nv12_back;
                        YU12_To_NV12_Tight(yu12.data(), W, H, nv12_back);
                        // 4) compare
                        if (nv12_src.size() != nv12_back.size()) {
                            printf("Size mismatch: src=%zu back=%zu\n", nv12_src.size(), nv12_back.size());
                        } else {
                            size_t firstDiff = (size_t)-1;
                            for (size_t i = 0; i < nv12_src.size(); ++i) {
                                if (nv12_src[i] != nv12_back[i]) { firstDiff = i; break; }
                            }
                            if (firstDiff == (size_t)-1) {
                                printf("Round-trip NV12 match: conversion is correct.\n");
                            } else {
                                // Determine whether the difference falls in Y or UV
                                size_t ySize = W * H;
                                const char* plane = (firstDiff < ySize) ? "Y" : "UV";
                                size_t off = (firstDiff < ySize) ? firstDiff : (firstDiff - ySize);

                                if (plane[0] == 'Y') {
                                    int row = int(off / W), col = int(off % W);
                                    printf("Mismatch in %s plane at (%d,%d): src=%u back=%u\n",
                                        plane, row, col, nv12_src[firstDiff], nv12_back[firstDiff]);
                                } else {
                                    int row = int(off / W);
                                    int col = int(off % W);
                                    printf("Mismatch in %s plane at (row=%d, byteCol=%d): src=%u back=%u\n",
                                        plane, row, col, nv12_src[firstDiff], nv12_back[firstDiff]);
                                }
                            }
                        }
                    }
                    #endif
                }
                    
                    VPP_SYS_UnmapSurface(hdl, &surf);
                    // printf("Y=%u U=%u V=%u\n", yu12Buf[0], yu12Buf[D1_W*D1_H], yu12Buf[D1_W*D1_H + (D1_W*D1_H)/4]);
                }
            
            frame_idx++;
            #endif

            #ifdef DECODE_ENABLE
            if (write_file == true && i%skip_frame == 0) {
                // std::cout << ("send encode, stream " + std::to_string(stream_id)) << std::endl;
                VPP_ENCODE_STREAM_SendFrame(encode_id, hdl, 0);
            }

            VPP_DECODE_STREAM_ReleaseFrame(decode_id, hdl);
            usleep(40'000);

            if (write_file == true && i%skip_frame == 0) {
                // get frame from encode
                VPP_ENCODE_STREAM_OutputBuffer *pOutputBuffer = (VPP_ENCODE_STREAM_OutputBuffer *)malloc(sizeof(VPP_ENCODE_STREAM_OutputBuffer));
                // std::cout << ("get encode, stream "+ std::to_string(stream_id)) << std::endl;
                sts = VPP_ENCODE_STREAM_GetEncodedData(encode_id, pOutputBuffer, 10000);
                if(sts!=VPP_STATUS_SUCCESS)
                {
                    free(pOutputBuffer);
                    i++;
                    continue;
                }
                //save frame
                if(write_file) {
                    FILE* outputfile;
                    std::string jpeg_path = "./output/" + output_profix + std::to_string(stream_id) + "-" + std::to_string(i) + ".jpg";
                    if((outputfile=fopen(jpeg_path.c_str(), "wb"))==NULL)
                    {
                        std::cout<<jpeg_path<<std::endl;
                        VPP_ENCODE_STREAM_ReleaseEncodedData(encode_id, pOutputBuffer);
                        free(pOutputBuffer);
                        i++;
                        continue;
                    }
                    fwrite(pOutputBuffer->pAddr,pOutputBuffer->Length,1,outputfile);
                    fclose(outputfile);
                }
                std::cout << ("release data, stream "+ std::to_string(stream_id)) << std::endl;
                VPP_ENCODE_STREAM_ReleaseEncodedData(encode_id, pOutputBuffer);
                free(pOutputBuffer);
            }
            #endif
            i++;
        }
        VPP_DECODE_STREAM_Stop(stream_id);
        // VPP_DECODE_STREAM_Destroy(stream_id);

        return 0;
    };

    std::vector<std::thread> vecFeed, vecProc;
    vecFeed.reserve(STREAM_NUM);
    vecProc.reserve(STREAM_NUM);

    for (int i = 0; i < STREAM_NUM; i++) {
        int32_t stream_id = i;
        // usleep(1000'000);
        if(write_file) {
            int32_t encode_id = stream_id;
            VPP_ENCODE_JPEG_Attr JPEG_Attr;
            JPEG_Attr.JPEGQualityLevel = quality;
            
            VPP_ENCODE_STREAM_Attr encodeAttr;
            encodeAttr.InputHeight=480;
            encodeAttr.InputWidth=720;
            encodeAttr.OutputRingBufferSize=0;
            encodeAttr.CodecStandard=VPP_CODEC_STANDARD_JPEG;
            encodeAttr.JpegAttr=JPEG_Attr;

            VPP_ENCODE_STREAM_Create(encode_id, &encodeAttr);
            std::cout<<"VPP_ENCODE_STREAM_Create Done "<<std::endl;
            VPP_ENCODE_STREAM_Start_RecvPicture(encode_id);
            std::cout<<"VPP_ENCODE_STREAM_Start 1 Done "<<std::endl;
        }
        
        // Create decode stream1:
        #ifdef DECODE_ENABLE
        int32_t decode_id = stream_id;
        VPP_DECODE_STREAM_Attr attr_1;
        // attr_1.CodecStandard = VPP_CODEC_STANDARD_H265;
        attr_1.CodecStandard = codec;
        attr_1.OutputFormat = VPP_PIXEL_FORMAT_NV12;
        attr_1.OutputHeight = 480;
        attr_1.OutputWidth = 720;
        attr_1.OutputBufQueueLength = 0;
        attr_1.RingBufferSize = 0;
        attr_1.InputMode = VPP_DECODE_INPUT_MODE_STREAM;
        // attr_1.InputMode = VPP_DECODE_INPUT_MODE_FRAME;
        VPP_DECODE_STREAM_Create(decode_id, &attr_1);
        std::cout<<"VPP_DECODE_STREAM_Create 1 Done "<<std::endl;
        VPP_DECODE_STREAM_SetOutputMode(decode_id, VPP_DECODE_OUTPUT_MODE_PLAYBACK);
        VPP_DECODE_STREAM_Start(decode_id);
        #endif

        if(input_mode == "rtsp") {
            // RTSP Open (keep reader alive in readers[])
            readers[stream_id] = std::make_shared<BitstreamRTSPReader>();
            std::string rtsp_url = urls[stream_id];
            std::cout << "Open url: " << rtsp_url << std::endl;

            #define SVET_RTSP_RETRY_MAX 5
            int retry = 5;
            while (retry-- > 0) {
                if (0 != readers[stream_id]->Open(rtsp_url.c_str())) {
                    printf("VPPSDK: {} Decode({}) Open {} failed. Will re-try\n");
                    // usleep(5000);
                } else {
                    break;
                }
            }
            if (retry <= 0) {
                printf("VPPSDK: {} Decode({}) Open {} failed. Decode init failed\n");
                return -1;
            } else {
                printf("VPPSDK: Connected to {}\n");
            }
        
            vecFeed.emplace_back(workload_feed, stream_id);
        }
        else { 
            // 仅启动 workload_feed_file
            vecFeed.emplace_back(workload_feed_file, stream_id);
        }

        #ifdef DECODE_ENABLE
        vecProc.emplace_back(workload_proc, stream_id);
        #endif
        std::this_thread::sleep_for(std::chrono::milliseconds(20));

    }

    std::this_thread::sleep_for(std::chrono::seconds(running_time));

    #ifdef DECODE_ENABLE
    flagProc.store(false);
    for (auto& t : vecProc) t.join();
    #endif
    
    
    flagFeed.store(false);
    for (auto& t : vecFeed) t.join();
    
    for (int i = 0; i < STREAM_NUM; ++i) {
        if (readers[i]) readers[i]->Close();   // RequestStop()
        // printf("closing readers[%d]\n", i);
    }
    BitstreamRTSPReader::StopEventLoop();
    
    #ifdef DECODE_ENABLE
    for (int i = 0; i < STREAM_NUM; ++i) {
        // VPP_DECODE_STREAM_Stop(i);
        VPP_DECODE_STREAM_Destroy(i);
    }
    #endif

    VPP_DeInit();
}
