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


#include "spdlog/spdlog.h"
#include "decode.h"
#include "bitstream_file_reader.h"
#include "video_pipeline.h"

#ifdef RTSP_ENABLE
#include "bitstream_rtsp_reader.h"
#endif
//#define VPPSDK_DEC
#ifdef VPPSDK_DEC
#include <vpp_common.h>
#include <vpp_decode.h>
#include <vpp_system.h>
#endif

#include <chrono>

using namespace SVET_APP;
using spdlog::debug;
using spdlog::error;
using spdlog::info;
using spdlog::warn;
using std::string;
using namespace std;

const string Decode::RTSP_URL_PREFIX = "rtsp://";

#ifdef VPPSDK_DEC
int CodecStrToType(string codec, VPP_CODEC_STANDARD &vpp_codec) {
    const string h264str = "h264";
    const string h265str = "h265";
    const string jpegstr = "jpeg";
    if (codec == h264str)
        vpp_codec =  VPP_CODEC_STANDARD_H264;
    else if (codec == h265str)
        vpp_codec = VPP_CODEC_STANDARD_H265;
    else if (codec == jpegstr)
        vpp_codec = VPP_CODEC_STANDARD_JPEG;
    else {
        error("SVET app: {} codec {} not supported", __func__, codec);
        return SVET_ERR_INVALID_PARA;
    }
    return 0;
}
#endif
int Decode::init(NewDecPara *para) {
    mId = para->id;

    if (para->dump.length() > 0 && (!mDumpFile)) {
        mDumpFile = fopen(para->dump.c_str(), "w+");
        if (!mDumpFile) {
            error("SVET app: {} failed to create rtsp dump file {}", __func__, para->dump);
        }
    }

    mLoopInput = para->loopInput;

    if (mState == NodeState::Uninitialized) {
        if (para->sfcEnable) {
            debug("SVET app: call VPP_DECODE_STREAM_Create(id:{}, codec:{}, outsize: {}x{}), loopInput:{}",
                  mId, para->codec, para->decW, para->decH, mLoopInput);
        } else {
            debug("SVET app: call VPP_DECODE_STREAM_Create(id:{}, codec:{}), loopInput:{}",
            mId, para->codec, mLoopInput);
        }
#ifdef VPPSDK_DEC
        VPP_DECODE_STREAM_Attr attr = {0};
        int res = CodecStrToType(para->codec, attr.CodecStandard);
        if (res < 0) {
            return res;
        }

        attr.OutputFormat = VPP_PIXEL_FORMAT_NV12;
        attr.InputMode = VPP_DECODE_INPUT_MODE_STREAM;

        if (para->sfcEnable) {
            attr.OutputWidth = para->decW;
            attr.OutputHeight = para->decH;
        }
        VPP_STATUS sts = VPP_DECODE_STREAM_Create(mId, &attr);
        CHK_VPPSDK_RET(sts, "VPP_DECODE_STREAM_Create");
#endif
        if (!mBuf) {
            mBuf = new char[mBufSize];
        }
        if (para->input.rfind(RTSP_URL_PREFIX) == 0) {
            mIsRtsp = true;
#ifdef RTSP_ENABLE
            mReader = std::make_shared<BitstreamRTSPReader>();
            #define SVET_RTSP_RETRY_MAX 5
            int count = 5;
            while (count-- > 0) {
                if (0 != mReader->Open(para->input.c_str())) {
                    error("SVET app: {} Decode({}) Open {} failed. Will re-try", __func__, mId, para->input.c_str());
                } else {
                    break;
                }
            }
            if (count <= 0) {
                error("SVET app: {} Decode({}) Open {} failed. Decode init failed", __func__, mId, para->input.c_str());
                return -1;
            } else {
                info("SVET app: Connected to {}", para->input.c_str());
            }
#else
            error("SVET app: RTSP input isn't supported");
            return -1;
#endif

        } else {
            mReader = std::make_shared<BitstreamFileReader>();
            if (0 != mReader->Open(para->input.c_str())) {
                error("SVET app: Open failed", __func__, para->input.c_str());
                return -1;
            }
            debug("SVET app: {} Open decode({}) input {} successes", __func__, mId, para->input);
        }
        mState = NodeState::Initialized;
    } else {
        error("SVET app: {} Decode state is not correct. expect {}, but it's {}",
               __func__, (int)NodeState::Uninitialized, (int)mState);
        return -1;
    }


    return 0;
}

int Decode::start() {
    if (mState != NodeState::Initialized && mState != NodeState::Stop) {
        error("SVET app: {} decoder {} state {} isn't {}", __func__, mId, (int)mState, (int)NodeState::Initialized);
        return SVET_ERR_WRONG_STATE;
    }

    if (!mThread) {
        mThread = std::make_shared<std::thread>(&Decode::loop, this);
    }

    if (mState != NodeState::Play) {
        debug("SVET app: call VPP_DECODE_STREAM_Start({})", mId);
#ifdef VPPSDK_DEC
        VPP_STATUS sts = VPP_DECODE_STREAM_Start(mId);
        CHK_VPPSDK_RET(sts, "VPP_DECODE_STREAM_Start");
#endif
        debug("SVET app: {} decode {} set state to Play", __func__, mId);
        DecodeStateReq reqMsg;
        reqMsg.reqState = NodeState::Play;
        mMsgQueue.push_back(reqMsg);
    }
    return 0;
}

//loop() must be called  when state is play after init()
void Decode::loop() {
    unsigned long long frameNum = 0;
    bool toExist = false;

    debug("SVET app: decode({}) loop: wait for Start signal", mId);
    while (true) {
        if (mMsgQueue.size() == 0) {
            //Wait for start() called by other thread
            if (mState != NodeState::Play) {

                auto msg = mMsgQueue.front();
                mMsgQueue.pop_front();
                debug("SVET app: decode({}) loop: received msg {}", mId, int(msg.reqState));
                if (msg.reqState == NodeState::Destroy) {
                    return;
                }
                else if (msg.reqState == NodeState::Play){
                    mState = NodeState::Play;
                    continue;
                }
            }
            else {
                play();
            }
        } else {
                auto msg = mMsgQueue.front();
                mMsgQueue.pop_front();
                if (msg.reqState == NodeState::Destroy) {
                    return;
                }
                else if (msg.reqState == NodeState::Play){
                    mState = NodeState::Play;
                    continue;
                }
        }
    }

    return;
}

Decode::~Decode() {
    try {
        debug("SVET app: decode {} deconstruct",(int)mId);
        if (mThread) {
            mThread->join();
        }
        if (mBuf) {
            delete [] mBuf;
            mBuf = nullptr;
        }
        if (mReader)
            mReader->Close();

        if (mDumpFile) {
            fclose(mDumpFile);
            mDumpFile = nullptr;
        }
    } catch (...) {
        std::cerr<<"SVET app: "<<__func__<<" unknown exception"<<std::endl;
    }
}

int Decode::destroy() {
    debug("SVET app: {} decode {} set state to Destroy", __func__, mId);
    if (mState != NodeState::Destroy) {

        bool toexit;
        handleStateChangeReq(NodeState::Destroy, toexit);

        mState = NodeState::Destroy;

        DecodeStateReq reqMsg;
        reqMsg.reqState = NodeState::Destroy;
        mMsgQueue.push_back(reqMsg);
    } else {
        warn("SVET app: {} decode {} state should be stop not {}", __func__, int(mState));
        return -1;
    }

    debug("SVET app: decode {} exited", mId);
    return 0;
}

int Decode::stop() {
    debug("SVET app: decode {} set state to Stop", mId);
    if (mState != NodeState::Play) {
        debug("SVET app: {} expected state play, current state {}", __func__, int(mState));
    }

    if (mState != NodeState::Stop) {
        bool toexit;
        handleStateChangeReq(NodeState::Stop, toexit);
        mState = NodeState::Stop;
    }
    return 0;
}

int Decode::play() {

#ifdef VPPSDK_DEC
    VPP_DECODE_STREAM_InputBuffer inputbuf;

    inputbuf.pAddr = (uint8_t*)mBuf;
    inputbuf.BasePts = 0;
    inputbuf.FlagEOStream = false;
    inputbuf.FlagEOFrame = false;
#endif
    if (!mReachEOF)
        debug("SVET app: decode({}) loop: try to read frame {}", mId, mFrameNum);
        
    int retBytes = mReader->Read(mBuf, mBufSize);
    #define FEED_DECODE_MIN_SIZE 64
    int readCount = 1;
    if  (retBytes > 0) {
        mReachEOF = false;
        char *ptr = mBuf;

        if (retBytes < FEED_DECODE_MIN_SIZE) {
            for (int i = 0; i < 10; i++) {
                 ptr = mBuf + retBytes;
                 int bytes = mReader->Read(ptr, mBufSize - retBytes);
                 if  (bytes > 0) {
                    retBytes += bytes;
                    if (bytes < FEED_DECODE_MIN_SIZE) {
                        continue;
                    }
                    else
                        break;
                 }
                 else {
                    error("SVET app: decode {} {} mReader->Read() return {}", __func__, mId, bytes);
                    break;
                 }
            }           

        }
        
        debug("SVET app: call VPP_DECODE_STREAM_FeedInput({}, ) buf size {} frame {} state {}", mId, retBytes, mFrameNum, (int)mState);
#ifdef VPPSDK_DEC
#ifdef DEC_DEBUG
        chrono::high_resolution_clock::time_point time1,time2;
        chrono::duration<double> diff;
        time1 = chrono::high_resolution_clock::now();
#endif

        inputbuf.Length = retBytes;

#ifdef DEC_DEBUG
        VPP_DECODE_QUERY_DATA status;
        VPP_DECODE_STREAM_QueryStatus(mId, &status);
#endif
            VPP_STATUS sts = VPP_DECODE_STREAM_FeedInput(mId, &inputbuf, -1);
            unsigned int count = 0;

            while (sts ==  VPP_STATUS_ERR_DECODE_RINGBUFFER_FULL && count++ < SENDINPUT_RETRY) {//TBD wait for decoder 's error code define
                std::this_thread::sleep_for(std::chrono::microseconds(SENDINPUT_INTERVAL ));
                sts = VPP_DECODE_STREAM_FeedInput(mId, &inputbuf, -1);
            }

            if (sts != VPP_STATUS_SUCCESS && mState == NodeState::Play) {
                error("SVET app: VPP_DECODE_STREAM_FeedInput({},) return {}. retry count {}", mId, int(sts), count);
                stop();
                return sts;
            }
#ifdef DEC_DEBUG
            time2 = chrono::high_resolution_clock::now();
            diff = time2 - time1;
            if (mId == 0) {
              cout<<"decode  "<<mFrameNum<<" "<<diff.count() * 1000.0<<" left internal buffer "<<status.LeftBitstreamSize<< endl;
	    }
#endif
#else
            usleep(3000);
#endif
            mFrameNum++;

            if (mDumpFile) {
                auto writeSize = fwrite(mBuf, 1, retBytes, mDumpFile);
                debug("SVET app: {} save {} bytes to file", __func__, writeSize);
            }
    } else {
        if (!mIsRtsp) { 
            if (mLoopInput) {
                debug("SVET app: {}( {}) read end of input. Reset to read from the beginning", __func__, mId);
                mReader->Reset();
                play();
            } else {
                if (!mReachEOF) {
                    info("SVET app: {} decode({}) reach end of stream", __func__, mId);
                    mReachEOF = true;
                }
                usleep(SLEEP_US_AFTER_EOF); //TBD: shall reset reader or drain decode queue until all data decoded then call stop()

            }
        }
    }
    return 0;
}

int Decode::handleStateChangeReq(NodeState reqState, bool &toExit) {
    toExit = false;
    switch (reqState) {
        case NodeState::Play:
            mState = NodeState::Play;
            break;
        case NodeState::Stop:
        {
            mState = NodeState::Stop;
            debug("SVET app: call VPP_DECODE_STREAM_Stop({})", mId);
#ifdef VPPSDK_DEC
            VPP_STATUS sts = VPP_DECODE_STREAM_Stop(mId);
            CHK_VPPSDK_RET(sts, "VPP_DECODE_STREAM_Stop");
#endif
        }
            break;
        case NodeState::Destroy: {
            mState = NodeState::Destroy;
            debug("SVET app: call VPP_DECODE_STREAM_Destroy({})", mId);
#ifdef VPPSDK_DEC
           VPP_STATUS sts= VPP_DECODE_STREAM_Destroy(mId);
#endif
            debug("SVET app: decode({}) loop: exit ", mId);
            toExit = true;
#ifdef VPPSDK_DEC
            CHK_VPPSDK_RET(sts, "VPP_DECODE_STREAM_Destroy");
#endif
            return 0;
        }
            break;
        case NodeState::Uninitialized:
        case NodeState::Initialized:
        default:
            error("SVET app: decode({}) loop: wrong required state {}", mId, int(reqState));
            break;
    }
    return 0;
}

int Decode::enableUserPic(int w, int h, bool flagInstant, void *data) {
    debug("SVET app: {} call VPP_DECODE_STREAM_SetUserPicture({}, {}, {}, {})", __func__,
          mId, w, h, data);
    debug("SVET app: {} call VPP_DECODE_STREAM_EnableserPicture({}, {})", __func__,
          mId, flagInstant);
#ifdef VPPSDK_DEC_USERPIC

    VPP_STATUS sts = VPP_DECODE_STREAM_SetUserPicture(mId,
                                                      static_cast<uint8_t *>(data),
                                                      w, h, VPP_PIXEL_FORMAT_NV12);
    CHK_VPPSDK_RET(sts, "VPP_DECODE_STREAM_SetUserPicture");
    sts = VPP_DECODE_STREAM_EnableUserPicture(mId, flagInstant);
    CHK_VPPSDK_RET(sts, "VPP_DECODE_STREAM_EnableUserPicture");
#endif
    return 0;
}

int Decode::disableUserPic() {
    debug("SVET app: {} call VPP_DECODE_STREAM_DisableUserPicture({})", __func__,
          mId);
#ifdef VPPSDK_DEC_USERPIC
    VPP_STATUS sts = VPP_DECODE_STREAM_DisableUserPicture(mId);
    CHK_VPPSDK_RET(sts, "VPP_DECODE_STREAM_DisableUserPicture");
#endif
    return 0;
}

int Decode::unbindFromSink(NodeId &sinkNode) {
    int retry = UNBIND_RETRY_TIMES;
    while (mState != NodeState::Stop) {
        if (retry == 0 ) {
            warn("SVET app: {} time out for wait decode state changed to stop"); 
            break;           
        }
        usleep(SLEEP_US_WAIT_STOP);
        retry--;
    }

#ifdef VPPSDK_DEC
    VPP_StreamIdentifier decId;
    decId.NodeType = NODE_TYPE_DECODE;
    decId.DeviceId = VPP_ID_NOT_APPLICABLE;
    decId.StreamId = mId;
    VPP_StreamIdentifier sinkId;
    int r = VideoPipelineInfo::unbindFromSink(decId, sinkId);
    sinkNode = VideoPipelineInfo::streamIdToNodeId(sinkId);

    return r;
#endif
    return 0;
}
