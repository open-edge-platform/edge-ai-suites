/*******************************************************************************
 * Copyright (C) 2020-2022 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#include "modules/inference_util/radar/radar_detection_helper.hpp"

namespace hce{

namespace ai{

namespace inference{


void fft_complex(ComplexFloat* datain, ComplexFloat* dataout,
                 uint16_t fft_len) {
  DFTI_DESCRIPTOR_HANDLE data_hand_;
  MKL_LONG status;
  status =
      DftiCreateDescriptor(&data_hand_, DFTI_SINGLE, DFTI_COMPLEX, 1, fft_len);
  status = DftiSetValue(data_hand_, DFTI_PLACEMENT, DFTI_NOT_INPLACE);
  status = DftiCommitDescriptor(data_hand_);
  status = DftiComputeForward(data_hand_, datain, dataout); 
  status = DftiFreeDescriptor(&data_hand_);
}

enum windowing_type { hanning = 1, hamming = 2 };

void windowing(windowing_type win_type, float* windowArray, int len) {
  float len_mult = 1 / (float)(len - 1);
  switch (win_type) {
    case 1:
      // break;
      // float len_mult = 1/(float)(len-1);
      for (int i = 0; i < len; i++) {
        windowArray[i] = 0.5 * (1 - cosf(i * 2 * M_PI * len_mult));
      }
      break;
    case 2:
      // float len_mult = 1/(float)(len-1);
      for (int i = 0; i < len; i++) {
        windowArray[i] = 0.54 + 0.46 * cosf(i * 2 * M_PI * len_mult);
      }
      break;
    default:
      break;
  }
}

void swap(ComplexFloat* data1, ComplexFloat* data2) {
  ComplexFloat temp = *data1;
  *data1 = *data2;
  *data2 = temp;
}
void fftshift(ComplexFloat* data, int count) {

  int half = (int)floor((float)count / 2);
  if (count % 2 == 0) {
    for (int k = 0; k < half; k++) {
      swap(&data[k], &data[k + half]);
    }
  } else {
    ComplexFloat tmp = data[0];
    for (int k = 0; k < half; k++) {
      data[k] = data[half + k + 1];
      data[half + k + 1] = data[k + 1];
    }
    data[half] = tmp;
  }
}

void OSCFAR::cfar_detection(){
  // doppler 1d cfar
    // HVA_DEBUG("oscfar");
    int doppler_guardLen = dopplerWinGuardLen_;
    int doppler_trainLen = dopplerWinTrainLen_;
    int dopplerLen = n_chirps_;


    std::vector<int> dopplerCfarList;
    float dopplerPFA = dopplerPfa_;
    float noise = 0;

    float cfarRDdoppler[n_samples_][n_chirps_];

    int first = doppler_trainLen + doppler_guardLen;
    int last = dopplerLen - doppler_trainLen - doppler_guardLen;
    std::vector<float> leftcell;
    std::vector<float> rightcell;
    // std::vector<float> statisticcell;
    float leftnoise;
    float rightnoise;
    // doppler cfar
    for (int i = 0; i < n_samples_; i++)
    {
      for (int j = first; j < last; j++)
      {
        leftcell.clear();
        rightcell.clear();
        leftnoise = 0;
        rightnoise = 0;

        for (int k = j - doppler_trainLen - doppler_guardLen;
             k < j - doppler_guardLen - 1; k++)
        {
          leftcell.push_back(RD_spec->at(i,k));
        }
        for (int k = j + doppler_guardLen + 1;
             k < j + doppler_trainLen + doppler_guardLen; k++)
        {
          rightcell.push_back(RD_spec->at(i,k));
        }

        // ca-cfar
        leftnoise =
            std::accumulate(std::begin(leftcell), std::end(leftcell), 0.0) /
            leftcell.size();
        rightnoise =
            std::accumulate(std::begin(rightcell), std::end(rightcell), 0.0) /
            rightcell.size();

        std::vector<float> noisecell(leftcell);
        noisecell.insert(noisecell.end(),rightcell.begin(), rightcell.end());
        int k = static_cast<int>(noisecell.size()*3/4);
        std::sort(noisecell.begin(), noisecell.end());
        noise = noisecell[k-1];

        float indexdb =RD_spec->at(i,j);
        // float targetSnr = indexdb - noise;
        float targetSnr = indexdb;
        float doppler_threshold = dopplerPFA * noise;
        if (targetSnr > doppler_threshold)
        {
          dopplerCfarList.push_back(j); // save dopplerIdx
          cfarRDdoppler[i][j] = 1;      // save result of RD doppler cfar detection
        }
      }

      // left edge
      for (int j = 0; j < first; j++)
      {
        leftcell.clear();
        rightcell.clear();
        leftnoise = 0;
        rightnoise = 0;

        for (int k = j + doppler_guardLen + 1;
             k < j + doppler_trainLen + doppler_guardLen; k++)
        {
          rightcell.push_back(RD_spec->at(i,k));
        }

        rightnoise =
            std::accumulate(std::begin(rightcell), std::end(rightcell), 0.0) /
            rightcell.size();

        std::vector<float> noisecell(leftcell);
        noisecell.insert(noisecell.end(),rightcell.begin(), rightcell.end());
        int k = static_cast<int>(noisecell.size()*3/4);
        std::sort(noisecell.begin(), noisecell.end());
        noise = noisecell[k-1];

        float indexdb = RD_spec->at(i,j);
        // float targetSnr = indexdb - noise;
        float targetSnr = indexdb;
        float doppler_threshold = dopplerPFA * noise * 2;
        if (targetSnr > doppler_threshold)
        {
          dopplerCfarList.push_back(j); // save dopplerIdx
          cfarRDdoppler[i][j] = 1;      // save result of RD doppler cfar detection
        }
      }

      // right edge
      for (int j = last; j < dopplerLen; j++)
      {
        leftcell.clear();
        rightcell.clear();
        leftnoise = 0;
        rightnoise = 0;

        for (int k = j - doppler_trainLen - doppler_guardLen; k < j; k++)
        {
          leftcell.push_back(RD_spec->at(i,k));
        }

        leftnoise =
            std::accumulate(std::begin(leftcell), std::end(leftcell), 0.0) /
            leftcell.size();

        std::vector<float> noisecell(leftcell);
        noisecell.insert(noisecell.end(),rightcell.begin(), rightcell.end());
        int k = static_cast<int>(noisecell.size()*3/4);
        std::sort(noisecell.begin(), noisecell.end());
        noise = noisecell[k-1];

        float indexdb = RD_spec->at(i,j);
        // float targetSnr = indexdb - noise;
        float targetSnr = indexdb;
        float doppler_threshold = dopplerPFA * noise * 2;
        if (targetSnr > doppler_threshold)
        {
          dopplerCfarList.push_back(j); // save dopplerIdx
          cfarRDdoppler[i][j] = 1;      // save result of RD doppler cfar detection
        }
      }
    }

    std::sort(dopplerCfarList.begin(), dopplerCfarList.end());

    dopplerCfarList.erase(
        std::unique(dopplerCfarList.begin(), dopplerCfarList.end()),
        dopplerCfarList.end()); // now has zero value

    // need to remove zero value
    if (dopplerCfarList[0] == 0)
    {
      dopplerCfarList.erase(dopplerCfarList.begin()); // erase position zero
    }

    if(dopplerCfarList.size()==0){
      HVA_ERROR("CFAR parameters need to be tuned, please change cfar parameter in RadarConfig.json.");
    }

    std::vector<PointListIndex> targetList;

    //
    // range cfar
    float rangePFA = rangePfa_;
    noise = 0;

    int range_trainLen = rangeWinTrainLen_;
    int range_guardLen = rangeWinGuardLen_;

    std::vector<PointListIndex> rangeCfarList;
    int rangeLen = n_samples_;

    // first = range_trainLen+ range_guardLen+1;
    first = range_trainLen + range_guardLen;
    last = rangeLen - range_trainLen - range_guardLen;

    std::vector<float> upcell;
    std::vector<float> downcell;
    float upnoise;
    float downnoise;

    for (auto j : dopplerCfarList)
    {

      // HVA_DEBUG("dopplerCfarList j: %d", j);
      for (int i = first; i < last; i++)
      {
        upcell.clear();
        downcell.clear();
        upnoise = 0;
        downnoise = 0;
        for (int k = i - range_trainLen - range_guardLen;
             k < i - range_guardLen - 1; k++)
        {
          upcell.push_back(RD_spec->at(k,j));
        }
        for (int k = i + range_guardLen + 1;
             k < i + range_trainLen + range_guardLen; k++)
        {
          downcell.push_back(RD_spec->at(k,j));
        }

        // ca-cfar
        upnoise = std::accumulate(std::begin(upcell), std::end(upcell), 0.0) /
                  upcell.size();
        downnoise =
            std::accumulate(std::begin(downcell), std::end(downcell), 0.0) /
            downcell.size();

        std::vector<float> noisecell(leftcell);
        noisecell.insert(noisecell.end(),rightcell.begin(), rightcell.end());
        int k = static_cast<int>(noisecell.size()*3/4);
        std::sort(noisecell.begin(), noisecell.end());
        noise = noisecell[k-1];

        float indexdb = RD_spec->at(i,j);
        // float targetSnr = indexdb - noise;
        float targetSnr = indexdb;
        float range_threshold = rangePFA * noise;
        if (targetSnr > range_threshold)
        {
          PointListIndex target;
          target.rangeIndex = i;
          target.dopplerIndex = j;
          targetList.push_back(target); // save dopplerIdx
          cfar_output_.RD_after_cfar[i][j] = indexdb / noise;
        }
      }

      // up edge
      for (int i = 0; i < first; i++)
      {
        // int rangeCfarIdx = i + guardLen + trainLen;
        upcell.clear();
        downcell.clear();
        upnoise = 0;
        downnoise = 0;

        for (int k = i + range_guardLen + 1;
             k < i + range_trainLen + range_guardLen; k++)
        {
          downcell.push_back(RD_spec->at(k,j));
        }

        // ca-cfar
        downnoise =
            std::accumulate(std::begin(downcell), std::end(downcell), 0.0) /
            downcell.size();

        std::vector<float> noisecell(leftcell);
        noisecell.insert(noisecell.end(),rightcell.begin(), rightcell.end());
        int k = static_cast<int>(noisecell.size()*3/4);
        std::sort(noisecell.begin(), noisecell.end());
        noise = noisecell[k-1];

        float indexdb = RD_spec->at(i,j);
        // float targetSnr = indexdb - noise;
        float targetSnr = indexdb;
        float range_threshold = rangePFA * noise * 2;
        if (targetSnr > range_threshold)
        {
          PointListIndex target;
          target.rangeIndex = i;
          target.dopplerIndex = j;
          targetList.push_back(target); // save dopplerIdx
          cfar_output_.RD_after_cfar[i][j] = indexdb / noise;
        }
      }

      // down edge

      for (int i = last; i < rangeLen; i++)
      {

        upcell.clear();
        downcell.clear();
        upnoise = 0;
        downnoise = 0;
        for (int k = i - range_trainLen - range_guardLen;
             k < i; k++)
        {
          upcell.push_back(RD_spec->at(k,j));
        }
        // ca-cfar
        upnoise = std::accumulate(std::begin(upcell), std::end(upcell), 0.0) /
                  upcell.size();

        std::vector<float> noisecell(leftcell);
        noisecell.insert(noisecell.end(),rightcell.begin(), rightcell.end());
        int k = static_cast<int>(noisecell.size()*3/4);
        std::sort(noisecell.begin(), noisecell.end());
        noise = noisecell[k-1];

        float indexdb = RD_spec->at(i,j);
        // float targetSnr = indexdb - noise;
        float targetSnr = indexdb;
        float range_threshold = rangePFA * noise * 4;
        if (targetSnr > range_threshold)
        {
          PointListIndex target;
          target.rangeIndex = i;
          target.dopplerIndex = j;
          targetList.push_back(target); // save dopplerIdx
          cfar_output_.RD_after_cfar[i][j] = indexdb / noise;
        }
      }
    }

    HVA_DEBUG("targetList size: %d", targetList.size());

    cfar_output_.numberDetected = targetList.size();
    // cfar_output_.SNRArray = (float*)malloc(sizeof(float)* cfar_output_.numberDetected);
    cfar_output_.SNRArray.resize(cfar_output_.numberDetected);
    PointList2D temp;
    for (int i = 0; i < targetList.size(); i++)
    {
      temp.range_index = targetList[i].rangeIndex;
      temp.doppler_index = targetList[i].dopplerIndex;
      // temp.snr = cfarRD[temp.range_index][temp.doppler_index];
      temp.snr = cfar_output_.RD_after_cfar[temp.range_index][temp.doppler_index];
      cfar_output_.points.push_back(temp);
      cfar_output_.SNRArray[i] = temp.snr;
    }

    HVA_DEBUG("cfar output size: %d", cfar_output_.numberDetected);
}

void CACFAR::cfar_detection(){

  // doppler 1d cfar
    int doppler_guardLen = dopplerWinGuardLen_;
    int doppler_trainLen = dopplerWinTrainLen_;
    int dopplerLen = n_chirps_;


    std::vector<int> dopplerCfarList;
    float dopplerPFA = dopplerPfa_;
    float noise = 0;

    float cfarRDdoppler[n_samples_][n_chirps_];

    int first = doppler_trainLen + doppler_guardLen;
    int last = dopplerLen - doppler_trainLen - doppler_guardLen;
    std::vector<float> leftcell;
    std::vector<float> rightcell;
    float leftnoise;
    float rightnoise;
    // doppler cfar
    for (int i = 0; i < n_samples_; i++)
    {
      for (int j = first; j < last; j++)
      {
        leftcell.clear();
        rightcell.clear();
        leftnoise = 0;
        rightnoise = 0;

        for (int k = j - doppler_trainLen - doppler_guardLen;
             k < j - doppler_guardLen - 1; k++)
        {
          leftcell.push_back(RD_spec->at(i,k));
        }
        for (int k = j + doppler_guardLen + 1;
             k < j + doppler_trainLen + doppler_guardLen; k++)
        {
          rightcell.push_back(RD_spec->at(i,k));
        }

        // ca-cfar
        leftnoise =
            std::accumulate(std::begin(leftcell), std::end(leftcell), 0.0) /
            leftcell.size();
        rightnoise =
            std::accumulate(std::begin(rightcell), std::end(rightcell), 0.0) /
            rightcell.size();

        noise = (leftnoise + rightnoise) / 2;

        float indexdb =RD_spec->at(i,j);
        // float targetSnr = indexdb - noise;
        float targetSnr = indexdb;
        float doppler_threshold = dopplerPFA * noise;
        if (targetSnr > doppler_threshold)
        {
          dopplerCfarList.push_back(j); // save dopplerIdx
          cfarRDdoppler[i][j] = 1;      // save result of RD doppler cfar detection
        }
      }

      // left edge
      for (int j = 0; j < first; j++)
      {
        leftcell.clear();
        rightcell.clear();
        leftnoise = 0;
        rightnoise = 0;

        for (int k = j + doppler_guardLen + 1;
             k < j + doppler_trainLen + doppler_guardLen; k++)
        {
          rightcell.push_back(RD_spec->at(i,k));
        }

        rightnoise =
            std::accumulate(std::begin(rightcell), std::end(rightcell), 0.0) /
            rightcell.size();

        noise = (leftnoise + rightnoise) / 2;
        float indexdb = RD_spec->at(i,j);
        // float targetSnr = indexdb - noise;
        float targetSnr = indexdb;
        float doppler_threshold = dopplerPFA * noise * 2;
        if (targetSnr > doppler_threshold)
        {
          dopplerCfarList.push_back(j); // save dopplerIdx
          cfarRDdoppler[i][j] = 1;      // save result of RD doppler cfar detection
        }
      }

      // right edge
      for (int j = last; j < dopplerLen; j++)
      {
        leftcell.clear();
        rightcell.clear();
        leftnoise = 0;
        rightnoise = 0;

        for (int k = j - doppler_trainLen - doppler_guardLen; k < j; k++)
        {
          leftcell.push_back(RD_spec->at(i,k));
        }

        leftnoise =
            std::accumulate(std::begin(leftcell), std::end(leftcell), 0.0) /
            leftcell.size();

        noise = (leftnoise + rightnoise) / 2;
        float indexdb = RD_spec->at(i,j);
        // float targetSnr = indexdb - noise;
        float targetSnr = indexdb;
        float doppler_threshold = dopplerPFA * noise * 2;
        if (targetSnr > doppler_threshold)
        {
          dopplerCfarList.push_back(j); // save dopplerIdx
          cfarRDdoppler[i][j] = 1;      // save result of RD doppler cfar detection
        }
      }
    }

    std::sort(dopplerCfarList.begin(), dopplerCfarList.end());

    dopplerCfarList.erase(
        std::unique(dopplerCfarList.begin(), dopplerCfarList.end()),
        dopplerCfarList.end()); // now has zero value

    // need to remove zero value
    if (dopplerCfarList[0] == 0)
    {
      dopplerCfarList.erase(dopplerCfarList.begin()); // erase position zero
    }

    if(dopplerCfarList.size()==0){
      HVA_ERROR("CFAR parameters need to be tuned, please change cfar parameter in RadarConfig.json.");
    }

    std::vector<PointListIndex> targetList;

    //
    // range cfar
    float rangePFA = rangePfa_;
    noise = 0;

    int range_trainLen = rangeWinTrainLen_;
    int range_guardLen = rangeWinGuardLen_;

    std::vector<PointListIndex> rangeCfarList;
    int rangeLen = n_samples_;

    // first = range_trainLen+ range_guardLen+1;
    first = range_trainLen + range_guardLen;
    last = rangeLen - range_trainLen - range_guardLen;

    std::vector<float> upcell;
    std::vector<float> downcell;
    float upnoise;
    float downnoise;

    for (auto j : dopplerCfarList)
    {

      // HVA_DEBUG("dopplerCfarList j: %d", j);
      for (int i = first; i < last; i++)
      {
        upcell.clear();
        downcell.clear();
        upnoise = 0;
        downnoise = 0;
        for (int k = i - range_trainLen - range_guardLen;
             k < i - range_guardLen - 1; k++)
        {
          upcell.push_back(RD_spec->at(k,j));
        }
        for (int k = i + range_guardLen + 1;
             k < i + range_trainLen + range_guardLen; k++)
        {
          downcell.push_back(RD_spec->at(k,j));
        }

        // ca-cfar
        upnoise = std::accumulate(std::begin(upcell), std::end(upcell), 0.0) /
                  upcell.size();
        downnoise =
            std::accumulate(std::begin(downcell), std::end(downcell), 0.0) /
            downcell.size();

        noise = (upnoise + downnoise) / 2;
        float indexdb = RD_spec->at(i,j);
        // float targetSnr = indexdb - noise;
        float targetSnr = indexdb;
        float range_threshold = rangePFA * noise;
        if (targetSnr > range_threshold)
        {
          PointListIndex target;
          target.rangeIndex = i;
          target.dopplerIndex = j;
          targetList.push_back(target); // save dopplerIdx
          cfar_output_.RD_after_cfar[i][j] = indexdb / noise;
        }
      }

      // up edge
      for (int i = 0; i < first; i++)
      {
        // int rangeCfarIdx = i + guardLen + trainLen;
        upcell.clear();
        downcell.clear();
        upnoise = 0;
        downnoise = 0;

        for (int k = i + range_guardLen + 1;
             k < i + range_trainLen + range_guardLen; k++)
        {
          downcell.push_back(RD_spec->at(k,j));
        }

        // ca-cfar
        downnoise =
            std::accumulate(std::begin(downcell), std::end(downcell), 0.0) /
            downcell.size();

        noise = (upnoise + downnoise) / 2;
        float indexdb = RD_spec->at(i,j);
        // float targetSnr = indexdb - noise;
        float targetSnr = indexdb;
        float range_threshold = rangePFA * noise * 2;
        if (targetSnr > range_threshold)
        {
          PointListIndex target;
          target.rangeIndex = i;
          target.dopplerIndex = j;
          targetList.push_back(target); // save dopplerIdx
          cfar_output_.RD_after_cfar[i][j] = indexdb / noise;
        }
      }

      // down edge

      for (int i = last; i < rangeLen; i++)
      {

        upcell.clear();
        downcell.clear();
        upnoise = 0;
        downnoise = 0;
        for (int k = i - range_trainLen - range_guardLen;
             k < i; k++)
        {
          upcell.push_back(RD_spec->at(k,j));
        }
        // ca-cfar
        upnoise = std::accumulate(std::begin(upcell), std::end(upcell), 0.0) /
                  upcell.size();

        noise = (upnoise + downnoise) / 2;
        float indexdb = RD_spec->at(i,j);
        // float targetSnr = indexdb - noise;
        float targetSnr = indexdb;
        float range_threshold = rangePFA * noise * 4;
        if (targetSnr > range_threshold)
        {
          PointListIndex target;
          target.rangeIndex = i;
          target.dopplerIndex = j;
          targetList.push_back(target); // save dopplerIdx
          cfar_output_.RD_after_cfar[i][j] = indexdb / noise;
        }
      }
    }

    HVA_DEBUG("targetList size: %d", targetList.size());

    cfar_output_.numberDetected = targetList.size();
    // cfar_output_.SNRArray = (float*)malloc(sizeof(float)* cfar_output_.numberDetected);
    cfar_output_.SNRArray.resize(cfar_output_.numberDetected);
    PointList2D temp;
    for (int i = 0; i < targetList.size(); i++)
    {
      temp.range_index = targetList[i].rangeIndex;
      temp.doppler_index = targetList[i].dopplerIndex;
      // temp.snr = cfarRD[temp.range_index][temp.doppler_index];
      temp.snr = cfar_output_.RD_after_cfar[temp.range_index][temp.doppler_index];
      cfar_output_.points.push_back(temp);
      cfar_output_.SNRArray[i] = temp.snr;
    }

    HVA_DEBUG("cfar output size: %d", cfar_output_.numberDetected);
}

// find nearest 2^n
static inline int fls(int x)
{
    int r;


    __asm__("bsrl %1,%0\n\t"
            "jnz 1f\n\t"
            "movl $-1,%0\n"
            "1:" : "=r" (r) : "rm" (x));
    return r+1;
}
static inline unsigned int roundup_pow_of_two(unsigned int x)
{
    return 1UL << fls(x - 1);
}

void RadarDetection::rangeEstimation(){
    int rangeLen = m_n_samples_;
    int N_fft = rangeLen; // find nearest 2^n
    // int N_fft = roundup_pow_of_two(rangeLen);
  
    // if rangeLen is not 2^n, need to do zero padding
    ComplexFloat* datain = new ComplexFloat[N_fft];
    ComplexFloat* dataout = new ComplexFloat[N_fft];
    float* windowArray;
  
    windowArray = (float*)malloc(sizeof(float) * N_fft);
    windowing(hanning, windowArray, rangeLen);  // gene
    for (int m = 0; m < m_n_vrx_; m++) {
      for (int l = 0; l < m_n_chirps_; l++) {
        for (int n = 0; n < N_fft; n++) {
          datain[n] = getData(n, l, m);
        }

        for (int i = 0; i < N_fft; i++) {
          datain[i] = datain[i] * windowArray[i];
        }
        fft_complex(datain, dataout, N_fft);

        for (int p = 0; p < N_fft; p++) {
            rangeProfilePtr->setValue(p, l, m, dataout[p]);
        }
      }
    }
    free(windowArray);
    delete []datain;
    delete []dataout;

};

void RadarDetection::dopplerEstimation(){
    int N_fft = m_n_chirps_;
    // int N_fft = roundup_pow_of_two(m_n_chirps_);
    TwoDimArray<ComplexFloat> avgChirp(m_n_samples_, m_n_vrx_);

    for (int i = 0; i < m_n_samples_; i++) {
      for (int m = 0; m < m_n_vrx_; m++) {
        for (int j = 0; j < m_n_chirps_; j++) {
          avgChirp.setValue(i, m, rangeProfilePtr->at(i, j, m) + avgChirp.at(i, m));
        }

        avgChirp.setValue(i, m, avgChirp.at(i, m) / m_n_chirps_);
        for (int j = 0; j < m_n_chirps_; j++) {
          rangeProfilePtr->setValue(i, j, m,
                                rangeProfilePtr->at(i, j, m) - avgChirp.at(i, m));
        }
      }
    }

    // doppler fft

    ComplexFloat* dopplerdatain = new ComplexFloat[N_fft];
    ComplexFloat* dopplerdataout = new ComplexFloat[N_fft];
    // uint16_t fft_doppler = m_n_chirps_;  // length

    float* dopplerwindowArray;
    // int dopplerLen = m_n_chirps_;
    dopplerwindowArray = (float*)malloc(sizeof(float) * N_fft);
    windowing(hanning, dopplerwindowArray,
              N_fft);  // generate array of n_samples

    for (int m = 0; m < m_n_vrx_; m++) {
      for (int n = 0; n < m_n_samples_; n++) {
        for (int l = 0; l < N_fft; l++) {
          dopplerdatain[l] = rangeProfilePtr->at(n, l, m);
        }
        // windowing
        for (int i = 0; i < N_fft; i++) {
          dopplerdatain[i] = dopplerdatain[i] * dopplerwindowArray[i];
        }

        fft_complex(dopplerdatain, dopplerdataout, N_fft);
        fftshift(dopplerdataout, N_fft);  // fftshift

        for (int p = 0; p < N_fft; p++) {
          dopplerProfilePtr->setValue(n, p, m, dopplerdataout[p]);
        }
      }
    }

    free(dopplerwindowArray);

    delete []dopplerdatain;
    delete []dopplerdataout;

};

void RadarDetection::non_coherent_combing(){

    for (int n = 0; n < m_n_samples_; n++) {
      for (int l = 0; l < m_n_chirps_; l++) {
        for (int m = 0; m < m_n_vrx_; m++) {
          float real_data = dopplerProfilePtr->at(n, l, m).real();
          float imag_data = dopplerProfilePtr->at(n, l, m).imag();
          float sqrt_data =
              sqrt(real_data * real_data + imag_data * imag_data);
          float temp_data = RadarBeforeCfarPtr->at(n, l) + sqrt_data;
          RadarBeforeCfarPtr->setValue(n, l, temp_data);
        }
      }
    }
  

}

void RadarDetection::cfarDetection(){
    
    if(radar_detection_config_.m_range_cfar_method_==1 &&radar_detection_config_.m_doppler_cfar_method_==1){
    //ca-cfar
      auto cfar_detection =std::make_shared<CACFAR>(radar_detection_config_, m_n_samples_, m_n_chirps_, RadarBeforeCfarPtr);

      cfar_detection->cfar_detection();

      cfar_output = cfar_detection->getOutput();
    }
    else if(radar_detection_config_.m_range_cfar_method_==4 &&radar_detection_config_.m_doppler_cfar_method_==4){
      //os-cfar
      auto cfar_detection =std::make_shared<OSCFAR>(radar_detection_config_, m_n_samples_, m_n_chirps_, RadarBeforeCfarPtr);

      cfar_detection->cfar_detection();

      cfar_output = cfar_detection->getOutput();
    }

}

void RadarDetection::doaEstimation(){

  
  std::shared_ptr<DOAEstimation> doa_estimator;
  HVA_DEBUG("aoa estimation type: %d", radar_detection_config_.m_aoa_estimation_type_);
  switch (radar_detection_config_.m_aoa_estimation_type_){
    case FFT:
      doa_estimator =std::make_shared<FFTAngleEstimation>(radar_basic_config_, dopplerProfilePtr);
      break;
    case CAPON:
      doa_estimator =std::make_shared<CaponAngleEstimation>(radar_basic_config_, dopplerProfilePtr);
      break;
    case MUSIC:
      doa_estimator =std::make_shared<MusicAngleEstimation>(radar_basic_config_, dopplerProfilePtr);
      break;
    case DBF:
      doa_estimator =std::make_shared<DBFAngleEstimation>(radar_basic_config_, dopplerProfilePtr);
      break;
    default:
      doa_estimator =std::make_shared<FFTAngleEstimation>(radar_basic_config_, dopplerProfilePtr);
      break;
  }

  if(doa_estimator){
    doa_estimator->setPeakSearchOutput(peak_output);
    doa_estimator->setCfarOutput(cfar_output);
    doa_estimator->init(peak_output.numberDetected);
    doa_estimator->doa_estimation();
    point_clouds = doa_estimator->getPCL();
}


}


void RadarDetection::peakGrouping(){
    int target_num = cfar_output.numberDetected;

    HVA_DEBUG("target_num: %d", target_num);
    peak_output.numberDetected = 0;
    for (int i = 0; i < target_num; i++)
    {
      int rangeIndex = cfar_output.points[i].range_index;
      int dopplerIndex = cfar_output.points[i].doppler_index;
      if (rangeIndex >= 1 && rangeIndex < m_n_samples_-1 && dopplerIndex >= 1 &&
          dopplerIndex < m_n_chirps_-1)
      {
        if (cfar_output.RD_after_cfar[rangeIndex][dopplerIndex] >
                cfar_output.RD_after_cfar[rangeIndex - 1][dopplerIndex] &&
            cfar_output.RD_after_cfar[rangeIndex][dopplerIndex] >
                cfar_output.RD_after_cfar[rangeIndex + 1][dopplerIndex] &&
            cfar_output.RD_after_cfar[rangeIndex][dopplerIndex] >
                cfar_output.RD_after_cfar[rangeIndex][dopplerIndex - 1] &&
            cfar_output.RD_after_cfar[rangeIndex][dopplerIndex] >
                cfar_output.RD_after_cfar[rangeIndex][dopplerIndex + 1])
        {
          peak_output.RD_peakSearch[rangeIndex][dopplerIndex] =
              cfar_output.RD_after_cfar[rangeIndex][dopplerIndex];
          PointList2D temp;
          temp.doppler_index = dopplerIndex;
          temp.range_index = rangeIndex;
          temp.snr =
              cfar_output.RD_after_cfar[temp.range_index][temp.doppler_index];
          peak_output.points.push_back(temp);
          peak_output.numberDetected++;
        }
      }
    }

    HVA_DEBUG("peak_output size: %d", peak_output.numberDetected);
}
void DOAEstimation::generateCompCoff(phaseParameter &phase_parameter, int speedBin,
                                                     std::vector<ComplexFloat> &compCoffVec)
{
    int txNum = phase_parameter.txAntenna;
    int rxNum = phase_parameter.rxAntenna;
    compCoffVec.resize(txNum * rxNum);
    float phi = 2 * PI * (speedBin - phase_parameter.dopplerBin / 2 - 1) /
                phase_parameter.dopplerBin;

    for (int txId = 0; txId < txNum; txId++)
    {
      for (int rxId = 0; rxId < rxNum; rxId++)
      {
        const int compCoffVec_index = txId * rxNum + rxId;
        compCoffVec[compCoffVec_index] = exp(-1 * sqrt(-1) * txId * phi);
      }
    }
}

void DOAEstimation::calculate_pcls(std::shared_ptr<pointClouds> &input, std::shared_ptr<pointClouds> &output, RadarBasicConfig &radar_basic_config)
{
    float light_speed_meter_per_sec = 299792458;
    float freq_slope_m_hz_per_usec = radar_basic_config.freqSlopeConst;
    float adc_sample_period_usec =
        1000 / radar_basic_config.adcSampleRate * radar_basic_config.adcSamples;
    float band_width = freq_slope_m_hz_per_usec * adc_sample_period_usec * 1e6;
    float range_resolution = light_speed_meter_per_sec / (2.0 * band_width);

    // doppler resolution
    float center_frequency = radar_basic_config.Start_frequency * 1e9 + band_width / 2;
    float chirp_interval = (radar_basic_config.rampEndTime + radar_basic_config.idle) * 1e-6;
    // TDM_MIMO Tchirp =(chirp_interval)*nTx
    float doppler_resolution = light_speed_meter_per_sec /
                               (2 * radar_basic_config.numChirps * radar_basic_config.numTx *
                                center_frequency * chirp_interval);

    // angle resolution
    float angle_resoluton =
        (float)2 / radar_basic_config.numRx / radar_basic_config.numTx * 180 / M_PI;
    output->num = input->num;
    // radical
    // output->rangeIdxArray= input->rangeIdxArray;
    // output->speedIdxArray =input->speedIdxArray;
    // for (int i = 0; i < input->num; i++)
    // {

    //   int rangeIdx = input->rangeIdxArray[i];
    //   int dopplerIdx = input->speedIdxArray[i];
    //   output->rangeFloat[i] = rangeIdx * range_resolution;
    //   output->speedFloat[i] =
    //       (dopplerIdx - n_chirps_ / 2) * doppler_resolution;
    // }
    // raddet dataset now need preprocessing 
    // output->rangeIdxArray= input->rangeIdxArray; 
    output->speedIdxArray =input->speedIdxArray;
    for (int i = 0; i < input->num; i++)
    {
      int rangeIdx = 256 - input->rangeIdxArray[i];
      // int rangeIdx = input->rangeIdxArray[i];
      int dopplerIdx = input->speedIdxArray[i];
      output->rangeIdxArray[i] = 256 - input->rangeIdxArray[i];
      output->rangeFloat[i] = rangeIdx * range_resolution;
      output->speedFloat[i] =
          (dopplerIdx - n_chirps_ / 2) * doppler_resolution;
    }
}
void FFTAngleEstimation::angleFFT(ComplexFloat* frameData, float& angle)
{

    int angleFFTNum = n_chirps_;
    // angle fft
    ComplexFloat* frameDataout = new ComplexFloat[angleFFTNum]();
    ComplexFloat* frameDatain = new ComplexFloat[angleFFTNum]();
    memcpy(frameDatain, frameData, n_vrx_*sizeof(ComplexFloat)); //zero padding

    fft_complex(frameDatain, frameDataout, angleFFTNum);
    // fftshift
    fftshift(frameDataout, angleFFTNum);

    std::vector<float> doa_abs;
    doa_abs = normComplexArray(frameDataout, angleFFTNum);
    // float maxValue = *max_element(doa_abs.begin(), doa_abs.end());
    int maxLoc = max_element(doa_abs.begin(), doa_abs.end()) -
                 doa_abs.begin(); 

    // angle = asin((maxLoc - angleFFTNum / 2) * 2 / angleFFTNum) * 180 / PI;
    std::vector<float> w = linspace((float)(-angleFFTNum / 2 / (angleFFTNum / 2)), (float)(angleFFTNum / 2 - 1) / (angleFFTNum / 2), angleFFTNum);

    //  std::vector<float> angle_axis = asin(w)*180/PI;
    std::vector<float> angle_axis;
    for (int i = 0; i < angleFFTNum; i++)
    {
      w[i] = asin(w[i]) * 180 / PI;
      angle_axis.push_back(w[i]);
    }
    angle = angle_axis[maxLoc];

    delete []frameDatain;
    delete []frameDataout;
}
void FFTAngleEstimation::doa_estimation()
{
    std::vector<float> angleArrays;
    // vector<int> angleIndexs;
    std::vector<int> rangeIndexs;
    std::vector<int> dopplerIndexs;
    std::vector<float> SNRArrays;
    angleArrays.clear();
    // angleIndexs.clear();
    rangeIndexs.clear();
    dopplerIndexs.clear();
    SNRArrays.clear();
    phaseParameter pha_param;
    pha_param = setPhaseParameters();
    for (int i = 0; i < peakOutput_.points.size(); i++)
    {
      int rangeIdx = peakOutput_.points[i].range_index;
      int dopplerIdx = peakOutput_.points[i].doppler_index;
      rangeIndexs.push_back(rangeIdx);
      dopplerIndexs.push_back(dopplerIdx);

      ComplexFloat* ant = new ComplexFloat[n_vrx_]();
      for(int k=0;k<n_vrx_; k++){
        ant[k] = doppler_profile_->at(rangeIdx, dopplerIdx, k);
      }

      // no phase compensation

      // int speedBin = dopplerIdx;
      // std::vector<ComplexFloat> compCoff;
      // generateCompCoff(pha_param, speedBin, compCoff);
      // std::vector<ComplexFloat> ant_comp;
      // // ant_comp = ant.*compCoff;
      // for (int j = 0; j < ant_comp.size(); j++)
      // {
      //   // complex mu
      //   ant_comp[j].real(ant[j].real() * compCoff[j].real() -
      //                    ant[j].imag() * compCoff[j].imag());
      //   ant_comp[j].imag(compCoff[j].imag() * ant[j].real() +
      //                    ant[j].real() * compCoff[j].imag());
      // }

      float ang;

      angleFFT(ant, ang); // no angle compensation

      angleArrays.push_back(-ang);
      SNRArrays.push_back(peakOutput_.points[i].snr);
      // calculate pcl
      delete []ant;
    }
    pointClouds_->rangeIdxArray = rangeIndexs;
    pointClouds_->speedIdxArray =dopplerIndexs;
    pointClouds_->aoaVar = angleArrays;
    pointClouds_->SNRArray =SNRArrays;

    pointClouds_->num = peakOutput_.points.size();
    // pointClouds_.SNRArray = cfar_output_.SNRArray;  

    calculate_pcls(pointClouds_, pointClouds_, radar_basic_config_);
}

void DBFAngleEstimation::angleDBF(ComplexFloat* frameData, float& angle)
{
  
  float deg[360];
  float dphi[n_vrx_];
  ComplexFloat doa_dbf[360];
  for (int i = 0; i < 360; i++) {
    ComplexFloat weightVec[n_vrx_];
    deg[i] = float(i - 180) / 2.0;
    for (int j = 0; j < n_vrx_; j++) {
      dphi[j] = j * 2 * PI * 0.5 * std::sin(deg[i] * PI / 180);
      weightVec[j] = std::exp(ComplexFloat(0, -dphi[j]));
    }

    ComplexFloat c[n_vrx_];

    ComplexFloat temp;
    ComplexFloat result;
    int rows = 1;
    int cols = n_vrx_;
    MKL_Complex8 alpha = {1.0, 0.0};
    MKL_Complex8 beta = {0.0, 0.0};
    int N =n_vrx_;
    cblas_cdotu_sub(N, frameData, 1, weightVec, 1, &result);
    doa_dbf[i] = result;
  }

  float res[360];
  for (int i = 0; i < 360; i++) {
    res[i] = std::sqrt(doa_dbf[i].imag() * doa_dbf[i].imag() +
                        doa_dbf[i].real() * doa_dbf[i].real());
  }
  int local_max = std::max_element(res, res+360) -res;
  angle = (local_max-180)/2.0f;

}

void DBFAngleEstimation::doa_estimation()
{
    std::vector<float> angleArrays;
    // vector<int> angleIndexs;
    std::vector<int> rangeIndexs;
    std::vector<int> dopplerIndexs;
    std::vector<float> SNRArrays;
    angleArrays.clear();
    // angleIndexs.clear();
    rangeIndexs.clear();
    dopplerIndexs.clear();
    SNRArrays.clear();
    phaseParameter pha_param;
    pha_param = setPhaseParameters();
    for (int i = 0; i < peakOutput_.points.size(); i++)
    {
      int rangeIdx = peakOutput_.points[i].range_index;
      int dopplerIdx = peakOutput_.points[i].doppler_index;
      rangeIndexs.push_back(rangeIdx);
      dopplerIndexs.push_back(dopplerIdx);

      ComplexFloat* ant = new ComplexFloat[n_vrx_]();
      for(int k=0;k<n_vrx_; k++){
        ant[k] = doppler_profile_->at(rangeIdx, dopplerIdx, k);
      }

      // no phase compensation

      // int speedBin = dopplerIdx;
      // std::vector<ComplexFloat> compCoff;
      // generateCompCoff(pha_param, speedBin, compCoff);
      // std::vector<ComplexFloat> ant_comp;
      // // ant_comp = ant.*compCoff;
      // for (int j = 0; j < ant_comp.size(); j++)
      // {
      //   // complex mu
      //   ant_comp[j].real(ant[j].real() * compCoff[j].real() -
      //                    ant[j].imag() * compCoff[j].imag());
      //   ant_comp[j].imag(compCoff[j].imag() * ant[j].real() +
      //                    ant[j].real() * compCoff[j].imag());
      // }

      float ang;

      angleDBF(ant, ang); // no angle compensation

      angleArrays.push_back(-ang);
      SNRArrays.push_back(peakOutput_.points[i].snr);
      // calculate pcl
      delete []ant;
    }
    pointClouds_->rangeIdxArray = rangeIndexs;
    pointClouds_->speedIdxArray =dopplerIndexs;
    pointClouds_->aoaVar = angleArrays;
    pointClouds_->SNRArray =SNRArrays;

    pointClouds_->num = peakOutput_.points.size();
    // pointClouds_.SNRArray = cfar_output_.SNRArray;  
    calculate_pcls(pointClouds_, pointClouds_, radar_basic_config_);
}


void CaponAngleEstimation::angleCapon(ComplexFloat* frameData, float& angle)
{

    ComplexDouble* frameDatain = new ComplexDouble[n_vrx_];
    for (int i = 0; i < n_vrx_; ++i) {
        frameDatain[i] = static_cast<ComplexDouble>(frameData[i]);
    }
    int n = n_vrx_;
    int n_Rxx = n*n;
    ComplexDouble Rxx[n_Rxx]={0};
    ComplexFloat Pmusic[360] = {0};
    
    MKL_Complex16 alpha = {1.0, 0.0};
    MKL_Complex16 beta = {0.0, 0.0};
    cblas_zgerc(CblasColMajor, n, n, &alpha, frameDatain, 1, frameDatain, 1, Rxx, n);

    // get inverse of Rxx

    lapack_int ipiv[n];
    int info;
    double lambda = 1e-8;
    for (int i = 0; i < n; ++i) {
        Rxx[i*n+i] += lambda;
    }
    info = LAPACKE_zgetrf(LAPACK_ROW_MAJOR, n, n, reinterpret_cast<lapack_complex_double*>(Rxx), n, ipiv);
    if (info < 0) {
        // info = 0: The function completed successfully.
        // info > 0: Indicates that the matrix is singular, and the value of info represents the position of the first zero pivot. For example, if info = 3,
        // it means that the third pivot element is zero, and the matrix is singular.
        // info < 0: Indicates that the -info-th parameter had an illegal value.
        HVA_ERROR("LAPACKE_zgetrf failed with error %d", info);
    }
    info = LAPACKE_zgetri(LAPACK_ROW_MAJOR, n, reinterpret_cast<lapack_complex_double*>(Rxx), n, ipiv);
    if (info < 0) {
        // info = 0: The function completed successfully.
        // info > 0: Indicates that the matrix is singular, and the value of info represents the position of the first zero pivot. For example, if info = 3,
        // it means that the third pivot element is zero, and the matrix is singular.
        // info < 0: Indicates that the -info-th parameter had an illegal value.
        HVA_ERROR("LAPACKE_zgetri failed with error %d", info);
    }

    double deg[360];
    double dphi[n_vrx_];
    ComplexDouble Pcapon[360];
    for (int i = 0; i < 360; i++) {
      ComplexDouble weightVec[n_vrx_];
      deg[i] = double(i - 180) / 2.0;
      for (int j = 0; j < n_vrx_; j++) {
        dphi[j] = j * 2 * PI * 0.5 * std::sin(deg[i] * PI / 180);
        ComplexDouble exponent(0.0, dphi[j]);
        weightVec[j] = std::exp(exponent);
      }

      ComplexDouble result;

      int vRx = n_vrx_;
      ComplexDouble tempVec[vRx];

      cblas_zgemv(CblasColMajor, CblasNoTrans, vRx, vRx, &alpha, Rxx, vRx,
                  weightVec, 1, &beta, tempVec, 1);

      for (int i = 0; i < vRx; ++i) {
        result += std::conj(weightVec[i]) * tempVec[i];
      }

      Pcapon[i] = ComplexDouble(1.0, 0.0) / (result);
    }

    float res[360];
    for (int i = 0; i < 360; i++) {
      res[i] = std::sqrt(Pcapon[i].imag() * Pcapon[i].imag() +
                         Pcapon[i].real() * Pcapon[i].real());
    }
    int local_max = std::max_element(res, res + 360) - res;
    angle = (local_max - 180) / 2.0f;

    delete[] frameDatain;
}

void CaponAngleEstimation::doa_estimation()
{
    std::vector<float> angleArrays;
    // vector<int> angleIndexs;
    std::vector<int> rangeIndexs;
    std::vector<int> dopplerIndexs;
    std::vector<float> SNRArrays;
    angleArrays.clear();
    // angleIndexs.clear();
    rangeIndexs.clear();
    dopplerIndexs.clear();
    SNRArrays.clear();
    phaseParameter pha_param;
    pha_param = setPhaseParameters();
    for (int i = 0; i < peakOutput_.points.size(); i++)
    {
      int rangeIdx = peakOutput_.points[i].range_index;
      int dopplerIdx = peakOutput_.points[i].doppler_index;
      rangeIndexs.push_back(rangeIdx);
      dopplerIndexs.push_back(dopplerIdx);

      ComplexFloat* ant = new ComplexFloat[n_vrx_]();
      for(int k=0;k<n_vrx_; k++){
        ant[k] = doppler_profile_->at(rangeIdx, dopplerIdx, k);
      }

      // no phase compensation

      // int speedBin = dopplerIdx;
      // std::vector<ComplexFloat> compCoff;
      // generateCompCoff(pha_param, speedBin, compCoff);
      // std::vector<ComplexFloat> ant_comp;
      // // ant_comp = ant.*compCoff;
      // for (int j = 0; j < ant_comp.size(); j++)
      // {
      //   // complex mu
      //   ant_comp[j].real(ant[j].real() * compCoff[j].real() -
      //                    ant[j].imag() * compCoff[j].imag());
      //   ant_comp[j].imag(compCoff[j].imag() * ant[j].real() +
      //                    ant[j].real() * compCoff[j].imag());
      // }

      float ang;

      angleCapon(ant, ang); // no angle compensation

      angleArrays.push_back(-ang);
      SNRArrays.push_back(peakOutput_.points[i].snr);
      // calculate pcl
      delete []ant;
    }
    pointClouds_->rangeIdxArray = rangeIndexs;
    pointClouds_->speedIdxArray =dopplerIndexs;
    pointClouds_->aoaVar = angleArrays;
    pointClouds_->SNRArray =SNRArrays;

    pointClouds_->num = peakOutput_.points.size();
    // pointClouds_.SNRArray = cfar_output_.SNRArray;  
    calculate_pcls(pointClouds_, pointClouds_, radar_basic_config_);
}

void MusicAngleEstimation::angleMusic(ComplexFloat* frameData, float& angle)
{
  ComplexFloat* frameDatain = new ComplexFloat[n_vrx_]();
  memcpy(frameDatain, frameData, n_vrx_ * sizeof(ComplexFloat));

  int n = n_vrx_;
  int nn = n * n;
  ComplexFloat Rxx[nn] = {0};
  ComplexFloat Pmusic[360] = {0};

  MKL_Complex8 alpha = {1.0, 0.0};
  MKL_Complex8 beta = {0.0, 0.0};
  MKL_INT lda = n_vrx_;

  cblas_cgerc(CblasColMajor, n, n, &alpha, frameDatain, 1, frameDatain, 1, Rxx, n);

  float s[n_vrx_];

  MKL_INT info;

  info = LAPACKE_cheevd(LAPACK_ROW_MAJOR, 'V', 'U', n, reinterpret_cast<MKL_Complex8*>(Rxx), lda, s);
  if (info > 0) {
    HVA_ERROR("The algorithm failed to compute eigenvalues.");
  }
  int n_En = n * (n - 1);
  ComplexFloat En[n_En];
  ComplexFloat Pn[nn];

  for (int i = 0; i < n; i++) {
    for (int j = 0; j < n / 2; j++) {
      ComplexFloat temp = Rxx[i * n + j];
      Rxx[i * n + j] = Rxx[i * n + (n - j - 1)];
      Rxx[i * n + (n - j - 1)] = temp;
    }
  }

  for (int i = 0; i < n; i++) {
    for (int j = 0; j < n; j++) {
      En[i * n + j] = Rxx[i * n + 1 + j];
    }
  }

  cblas_cgemm(CblasRowMajor, CblasNoTrans, CblasConjTrans, n, n, n - 1, &alpha,
              En, n, En, n, &beta, Pn, n);

  float deg[360];
  float dphi[n_vrx_];

  ComplexFloat I = ComplexFloat(0.0f, 1.0f);

  for (int i = 0; i < 360; i++) {
    ComplexFloat weightVec[n_vrx_];
    deg[i] = float(i - 180) / 2.0;
    for (int j = 0; j < n_vrx_; j++) {
      dphi[j] = j * 2 * PI * 0.5 * std::sin(deg[i] * PI / 180);
      ComplexFloat exponent(0.0f, dphi[j]);
      weightVec[j] = std::exp(exponent);
    }

    ComplexFloat result;

    int vRx = 8;
    ComplexFloat tempVec[vRx];

    cblas_cgemv(CblasColMajor, CblasNoTrans, vRx, vRx, &alpha, Pn, vRx,
                weightVec, 1, &beta, tempVec, 1);

    for (int i = 0; i < vRx; ++i) {
      result += std::conj(weightVec[i]) * tempVec[i];
    }

    Pmusic[i] = ComplexFloat(1) / (result);
  }

  float res[360];
  for (int i = 0; i < 360; i++) {
    res[i] = std::abs(Pmusic[i]);
  }

  int local_max = std::max_element(res, res + 360) - res;

  angle = (local_max - 180) / 2.0f;

  delete[] frameDatain;
}

void MusicAngleEstimation::doa_estimation()
{
    std::vector<float> angleArrays;
    // vector<int> angleIndexs;
    std::vector<int> rangeIndexs;
    std::vector<int> dopplerIndexs;
    std::vector<float> SNRArrays;
    angleArrays.clear();
    // angleIndexs.clear();
    rangeIndexs.clear();
    dopplerIndexs.clear();
    SNRArrays.clear();
    phaseParameter pha_param;
    pha_param = setPhaseParameters();
    for (int i = 0; i < peakOutput_.points.size(); i++)
    {
      int rangeIdx = peakOutput_.points[i].range_index;
      int dopplerIdx = peakOutput_.points[i].doppler_index;
      rangeIndexs.push_back(rangeIdx);
      dopplerIndexs.push_back(dopplerIdx);

      ComplexFloat* ant = new ComplexFloat[n_vrx_]();
      for(int k=0;k<n_vrx_; k++){
        ant[k] = doppler_profile_->at(rangeIdx, dopplerIdx, k);
      }

      // no phase compensation

      // int speedBin = dopplerIdx;
      // std::vector<ComplexFloat> compCoff;
      // generateCompCoff(pha_param, speedBin, compCoff);
      // std::vector<ComplexFloat> ant_comp;
      // // ant_comp = ant.*compCoff;
      // for (int j = 0; j < ant_comp.size(); j++)
      // {
      //   // complex mu
      //   ant_comp[j].real(ant[j].real() * compCoff[j].real() -
      //                    ant[j].imag() * compCoff[j].imag());
      //   ant_comp[j].imag(compCoff[j].imag() * ant[j].real() +
      //                    ant[j].real() * compCoff[j].imag());
      // }

      float ang;

      angleMusic(ant, ang); // no angle compensation

      angleArrays.push_back(-ang);
      SNRArrays.push_back(peakOutput_.points[i].snr);
      // calculate pcl
      delete []ant;
    }
    pointClouds_->rangeIdxArray = rangeIndexs;
    pointClouds_->speedIdxArray =dopplerIndexs;
    pointClouds_->aoaVar = angleArrays;
    pointClouds_->SNRArray =SNRArrays;

    pointClouds_->num = peakOutput_.points.size();
    // pointClouds_.SNRArray = cfar_output_.SNRArray;  
    calculate_pcls(pointClouds_, pointClouds_, radar_basic_config_);
}

void RadarDetection::runDetection(){
  rangeEstimation();
  // std::cout<<"debug test range estiamtion: "<<rangeProfilePtr->at(0,0,0)<<std::endl;
  dopplerEstimation();
  
  non_coherent_combing();
  // std::cout<<"debug test range estiamtion: "<<RadarBeforeCfarPtr->at(0,0)<<std::endl;
  cfarDetection();
  HVA_DEBUG("cfar output is: %d",cfar_output.numberDetected);
  // peakGrouping();
  // if (cfar_output.numberDetected < 100)  //alpha radical 50m
  if (cfar_output.numberDetected < 200) // raddet test
  {
    peak_output.numberDetected = cfar_output.numberDetected;
    peak_output.points = cfar_output.points;
    // peak_output.RD_peakSearch = cfar_output.RD_after_cfar;
    int target_num = cfar_output.numberDetected;
    for (int i = 0; i < target_num; i++)
    {
      int rangeIndex = cfar_output.points[i].range_index;
      int dopplerIndex = cfar_output.points[i].doppler_index;
      peak_output.RD_peakSearch[rangeIndex][dopplerIndex] =
          cfar_output.RD_after_cfar[rangeIndex][dopplerIndex];
    }
  }
  else
  {
    peakGrouping();
  }
  HVA_DEBUG("peak_output number detected is: %d", peak_output.numberDetected);
  // doa
  doaEstimation();

  HVA_DEBUG("point clouds number is %d", point_clouds->num);

}


}   // namespace inference

}   // namespace ai

}   // namespace hce