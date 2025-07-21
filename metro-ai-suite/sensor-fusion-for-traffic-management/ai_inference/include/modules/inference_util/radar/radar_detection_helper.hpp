/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2023 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef HCE_AI_INF_RADAR_DETECTION_HELPER_HPP
#define HCE_AI_INF_RADAR_DETECTION_HELPER_HPP

#include <vector>
#include <string>
#include <unordered_map>
#include <complex>
#include <iostream>
#include <cmath>  //exp
#include <algorithm>
#include <numeric>
#include <vector>
#include <cstring> //memcpy
#include <memory>
#include <algorithm>

#include <Eigen/Eigen>
#include <Eigen/Dense>
#include <Eigen/Eigenvalues> 

#include "mkl.h"
#include "mkl_dfti.h"
#include "inc/api/hvaLogger.hpp"
#include "nodes/radarDatabaseMeta.hpp"
#include "modules/inference_util/radar/complex_op.hpp"

namespace hce{

namespace ai{

namespace inference{

#define PI 3.141592653589793

template<typename T>
class TwoDimArray{
    
    public:
    // T* array;
    std::shared_ptr<T[]> array;
    int m_width;
    int m_height;


    public:
    using Ptr = std::shared_ptr<TwoDimArray>;
    TwoDimArray(int w, int h): m_width(w),m_height(h){
        array =std::shared_ptr<T[]>(new T[w*h]());
    }
    ~TwoDimArray(){}

    TwoDimArray(const TwoDimArray& obj){
        array = obj.array;
        m_width = obj.m_width;
        m_height =obj.m_height;
    }

    T at(int x, int y) const{
        return array[index(x, y)];

    }
    void setValue(int x, int y, T value){
        array[index(x,y)] = value;
    }
    protected:
    int index(int x, int y)const{
        return x+m_width*y;
        // return x*m_width +y;
    }

};
template<typename T>
class ThreeDimArray{

    public:
    // T* array;
    std::shared_ptr<T[]> array;
    int m_width;
    int m_height;
    int m_depth;

    public:
    using Ptr = std::shared_ptr<ThreeDimArray>;

    ThreeDimArray(int w, int h, int d):  m_width(w), m_height(h),m_depth(d){
        array =std::shared_ptr<T[]>(new T[w*h*d]());
    }

    ~ThreeDimArray(){};

    ThreeDimArray(const ThreeDimArray& obj){
        // copy constructor
        array = obj.array;
        m_width =obj.m_width;
        m_height =obj.m_height;
        m_depth =obj.m_depth;
    }

    void setValue(int x, int y, int z, T value){
        array[index(x,y,z)] = value;
    }

    std::shared_ptr<T[]> getArray(){
        return array;
    }

    T at(int x, int y, int z) const{
        return array[index(x, y, z)];
    }
    protected:
    int index(int x, int y, int z) const{
        return x*m_height+y +z*m_width*m_height;
    }
};

class RadarCube {
public:
    using Ptr = std::shared_ptr<RadarCube>;
    RadarCube(ComplexFloat* frame, int frame_size,int frame_idx, RadarBasicConfig radar_conf):frame_id(frame_idx),radar_basic_conf_(radar_conf),m_n_samples_(radar_conf.adcSamples),m_n_chirps_(radar_conf.numChirps),m_n_tx_(radar_conf.numTx), m_n_rx_(radar_conf.numRx),m_n_vrx_(radar_conf.numRx*radar_conf.numTx), radarCube_(radar_conf.adcSamples,radar_conf.numChirps,radar_conf.numRx*radar_conf.numTx) {
    //   frame_ = frame;
      frameSize_  = frame_size;
    //   radarCube_ = std::make_shared<ThreeDimArray<ComplexFloat>>(radar_conf.adcSamples,radar_conf.numChirps,radar_conf.numRx*radar_conf.numTx);
    };
    ~RadarCube(){}
    void  radarCube_format(ComplexFloat* frame){
        TwoDimArray<ComplexFloat> cdata(m_n_vrx_, m_n_samples_* m_n_chirps_);
        HVA_DEBUG("Debug frame[0] data: real%d, imag%d", (int)frame[0].real(), (int)frame[0].imag());
        for(int k=0;k<m_n_samples_* m_n_vrx_*m_n_chirps_;k++){
            int temp_chirp = k/(m_n_samples_* m_n_vrx_);
            int temp_sample = k%(m_n_samples_* m_n_vrx_);

            int line_rx = temp_sample/m_n_samples_;
            int sample_number = temp_sample%m_n_samples_;
          

            cdata.setValue(line_rx,temp_chirp*m_n_samples_+sample_number, frame[temp_chirp*m_n_vrx_*m_n_samples_+line_rx*m_n_samples_+sample_number] );
        }
       
        for(int k=0;k<m_n_vrx_; k++){
            for(int i=0;i<m_n_samples_; i++){
                for(int j=0;j<m_n_chirps_; j++){
                    radarCube_.setValue(i,j,k, cdata.at(k, j*m_n_samples_+i));
                
                }
            }
        }
        // for radical, other dataset need to verify the correctness
      
        // for (int k = 0; k < m_n_vrx_; k++) {
        //   for (int i = 0; i < m_n_samples_; i++) {
        //     for (int j = 0; j < m_n_chirps_; j++) {
        //       //nTX=2
        //      int vx = (k%m_n_rx_)*m_n_tx_ +k/m_n_rx_;
        //      radarCube_->setValue(i,j, vx, data_radar.at(i,j,k));

        //     }
        //   }
        // }
        
        // remove static clutter 
        TwoDimArray<ComplexFloat> avg(m_n_chirps_, m_n_vrx_);

        for (int j = 0; j < m_n_chirps_; j++)
        {
            for (int m = 0; m < m_n_vrx_; m++)
            {
                for (int i = 0; i < m_n_samples_; i++)
                {
                    avg.setValue(j, m, avg.at(j, m) + radarCube_.at(i, j, m));
                }
                avg.setValue(j, m, avg.at(j, m) / m_n_samples_); // need operater/
                for (int i = 0; i < m_n_samples_; i++)
                {
                    radarCube_.setValue(i, j, m, radarCube_.at(i, j, m) - avg.at(j, m));
                }
            }
        }

        HVA_DEBUG("radarCube_[0,31,7] data: real%d, imag%d", (int)radarCube_.at(0,31,7).real(), (int)radarCube_.at(0,31,7).imag());

    }

    std::shared_ptr<ComplexFloat[]> get_radar_cube_data(){
        return radarCube_.array;
    }

    int getRadarFrameSize(){
        return frameSize_;
    }

    ThreeDimArray<ComplexFloat>& getRadarCube(){
        return radarCube_;
    }


    ComplexFloat getData(int i,int j,int k){
        return radarCube_.at(i,j,k);
    }
 

private:

    // ComplexFloat* frame_;
    ThreeDimArray<ComplexFloat> radarCube_;
    RadarBasicConfig radar_basic_conf_;
    int frameSize_;
    const int m_n_samples_;
    const int m_n_chirps_;
    const int m_n_tx_;
    const int m_n_rx_;
    const int m_n_vrx_;
    int frame_id;
    
};

struct PointList2D {
  uint16_t range_index;
  uint16_t doppler_index;
  float snr;
};

struct detectionCFAR_output_
{

    int numberDetected;
    std::vector<std::vector<float>> RD_after_cfar;
    std::vector<PointList2D> points;
    std::vector<float> SNRArray;
};

struct peakSearch_output_
{

    int numberDetected;
    std::vector<std::vector<float>> RD_peakSearch;
    std::vector<PointList2D> points;
};

struct PointListIndex
{
    int rangeIndex;
    int dopplerIndex;
};

struct phaseParameter{
    int txAntenna;
    int rxAntenna;
    int dopplerBin;
    int virtualAntenna;
};

class CfarDetection
{
public:

    CfarDetection(RadarDetectionConfig radar_conf, int n_samples, int n_chirps, std::shared_ptr<TwoDimArray<float>>& RD) : cfar_conf(radar_conf), n_samples_(n_samples), n_chirps_(n_chirps){
        RD_spec = RD;
        cfar_output_.RD_after_cfar.resize(n_samples_);
        for(int i=0;i<n_samples_;i++){
            cfar_output_.RD_after_cfar[i].resize(n_chirps_);
        }
    };
    
    CfarDetection(){};
    ~CfarDetection(){};
    // non coherent combing
    // void non_coherent_combing();
    // cfar detection
    virtual void cfar_detection()=0;
    virtual detectionCFAR_output_& getOutput()=0;
    RadarDetectionConfig getConfig(){
        return cfar_conf;
    }
    void setCfarInput(std::shared_ptr<TwoDimArray<float>> rd){
        RD_spec = rd;
    }

private:
    RadarDetectionConfig cfar_conf;
    int n_chirps_;
    int n_samples_;

    std::shared_ptr<TwoDimArray<float>> RD_spec;
    detectionCFAR_output_ cfar_output_;

};

class CACFAR : public CfarDetection
{
public:
    CACFAR(RadarDetectionConfig radar_conf, int n_samples, int n_chirps, std::shared_ptr<TwoDimArray<float>> &RD) : n_samples_(n_samples), n_chirps_(n_chirps), dopplerPfa_(radar_conf.DopplerPfa), rangePfa_(radar_conf.RangePfa), dopplerWinGuardLen_(radar_conf.DopplerWinGuardLen), dopplerWinTrainLen_(radar_conf.DopplerWinTrainLen), rangeWinGuardLen_(radar_conf.RangeWinGuardLen), rangeWinTrainLen_(radar_conf.RangeWinTrainLen)
    {
        RD_spec = RD;
        cfar_output_.RD_after_cfar.resize(n_samples_);
        for (int i = 0; i < n_samples_; i++)
        {
            cfar_output_.RD_after_cfar[i].resize(n_chirps_);
        }
    };
    ~CACFAR(){};
    // CACFAR(){};
    void cfar_detection() override;
    detectionCFAR_output_& getOutput() override{
        return cfar_output_;
    }
private:
    std::shared_ptr<TwoDimArray<float>> RD_spec;
    detectionCFAR_output_ cfar_output_;
    int n_samples_;
    int n_chirps_;

    float dopplerPfa_;       // desired false alarm rate
    float rangePfa_;         // desired false alarm rate.
    int dopplerWinGuardLen_; // number of doppler cfar guard cells
    int dopplerWinTrainLen_; // number of doppler cfar training cells
    int rangeWinGuardLen_;   // number of range cfar guard cells
    int rangeWinTrainLen_;   // number of range cfar training cells
    // CfarMethod m_doppler_cfar_method_;                          // enum, doppler cfar method
    // CfarMethod m_range_cfar_method_;                            // enum, range cfar method
};

class OSCFAR : public CfarDetection
{
public:
    OSCFAR(RadarDetectionConfig radar_conf, int n_samples, int n_chirps, std::shared_ptr<TwoDimArray<float>> &RD) : n_samples_(n_samples), n_chirps_(n_chirps), dopplerPfa_(radar_conf.DopplerPfa), rangePfa_(radar_conf.RangePfa), dopplerWinGuardLen_(radar_conf.DopplerWinGuardLen), dopplerWinTrainLen_(radar_conf.DopplerWinTrainLen), rangeWinGuardLen_(radar_conf.RangeWinGuardLen), rangeWinTrainLen_(radar_conf.RangeWinTrainLen)
    {
        RD_spec = RD;
        cfar_output_.RD_after_cfar.resize(n_samples_);
        for (int i = 0; i < n_samples_; i++)
        {
            cfar_output_.RD_after_cfar[i].resize(n_chirps_);
        }
    };
    ~OSCFAR(){};
    void cfar_detection() override;
    detectionCFAR_output_& getOutput() override{
        return cfar_output_;
    }
private:
    std::shared_ptr<TwoDimArray<float>> RD_spec;
    detectionCFAR_output_ cfar_output_;
    int n_samples_;
    int n_chirps_;
    float kSite;

    float dopplerPfa_;       // desired false alarm rate
    float rangePfa_;         // desired false alarm rate.
    int dopplerWinGuardLen_; // number of doppler cfar guard cells
    int dopplerWinTrainLen_; // number of doppler cfar training cells
    int rangeWinGuardLen_;   // number of range cfar guard cells
    int rangeWinTrainLen_;   // number of range cfar training cells
};


class DOAEstimation{
    public:
    DOAEstimation(RadarBasicConfig& radar_basic_conf, std::shared_ptr<ThreeDimArray<ComplexFloat>>& doppler_profile): radar_basic_config_(radar_basic_conf){
        dopplerProfile_ = doppler_profile;
        n_samples_ = radar_basic_conf.adcSamples;
        n_chirps_ = radar_basic_conf.numChirps;
        n_vrx_ = radar_basic_conf.numRx * radar_basic_conf.numTx;
        cfar_output_.RD_after_cfar.resize(n_samples_);
        peakOutput_.RD_peakSearch.resize(n_samples_);
        for (int i = 0; i < n_samples_; i++)
        {
            cfar_output_.RD_after_cfar[i].resize(n_chirps_);
            peakOutput_.RD_peakSearch[i].resize(n_chirps_);
        }
    };
    DOAEstimation(){};
    ~DOAEstimation(){};
    virtual void init(int num) =0;
    virtual void doa_estimation()=0;
    virtual void setPeakSearchOutput(peakSearch_output_& peakOutput)=0;
    virtual void setCfarOutput(detectionCFAR_output_& cfarOutput)=0;
    virtual std::shared_ptr<pointClouds>& getPCL()=0;
    void generateCompCoff(phaseParameter& phase_parameter, int speedBin, std::vector<ComplexFloat>& compCoffVec);
    void calculate_pcls(std::shared_ptr<pointClouds>& input, std::shared_ptr<pointClouds>& output, RadarBasicConfig& radar_basic_config);
private:
    std::shared_ptr<ThreeDimArray<ComplexFloat>> dopplerProfile_;
    RadarBasicConfig radar_basic_config_;
    int n_samples_;
    int n_chirps_;
    int n_vrx_;
    peakSearch_output_ peakOutput_;
    detectionCFAR_output_ cfar_output_;
    // pointClouds pointClouds_;
    std::shared_ptr<pointClouds> pointClouds_;
    // radar_angle_estimation_method angle_estimation_method_;


};

class FFTAngleEstimation: public DOAEstimation
{
public:
    FFTAngleEstimation(RadarBasicConfig &radar_basic_conf, std::shared_ptr<ThreeDimArray<ComplexFloat>> &doppler_profile) : radar_basic_config_(radar_basic_conf),DOAEstimation(radar_basic_conf,doppler_profile)
    {
        doppler_profile_ = doppler_profile;
        n_samples_ = radar_basic_conf.adcSamples;
        n_chirps_ = radar_basic_conf.numChirps;
        n_vrx_ = radar_basic_conf.numRx * radar_basic_conf.numTx;

        pointClouds_ =std::make_shared<pointClouds>();
        cfar_output_.RD_after_cfar.resize(n_samples_);
        peakOutput_.RD_peakSearch.resize(n_samples_);
        for (int i = 0; i < n_samples_; i++)
        {
            cfar_output_.RD_after_cfar[i].resize(n_chirps_);
            peakOutput_.RD_peakSearch[i].resize(n_chirps_);
        }
    };
    ~FFTAngleEstimation(){}
    void doa_estimation() override;

    // pointClouds& getPCL()override{
    //     return pointClouds_;
    // }
    std::shared_ptr<pointClouds>& getPCL() override{
        return pointClouds_;
    }

    phaseParameter setPhaseParameters(){
        phaseParameter phaseParam;
        phaseParam.dopplerBin = radar_basic_config_.numChirps;
        phaseParam.rxAntenna = radar_basic_config_.numRx;
        phaseParam.txAntenna = radar_basic_config_.numTx;
        phaseParam.virtualAntenna = phaseParam.rxAntenna*phaseParam.txAntenna;
        return phaseParam;

    }

    void setPeakSearchOutput(peakSearch_output_& peakOutput) override{
        peakOutput_ = peakOutput;
    }
    void setCfarOutput(detectionCFAR_output_& cfarOutput) override{
        cfar_output_ = cfarOutput;
    }
    std::vector<float> normComplexArray(ComplexFloat *ComplexArray, int len)
    {

        std::vector<float> result;
        for (int i = 0; i < len; i++)
        {
                float temp = sqrt(ComplexArray[i].imag() * ComplexArray[i].imag() + ComplexArray[i].real() * ComplexArray[i].real());
                result.push_back(temp);
        }

        return result;
    }
    void angleFFT(ComplexFloat *frameData, float &angle);
    void init(int num)
    {
        pointClouds_->num = num;
        pointClouds_->rangeIdxArray.resize(num);
        pointClouds_->rangeFloat.resize(num);
        pointClouds_->speedIdxArray.resize(num);
        pointClouds_->speedFloat.resize(num);
        pointClouds_->aoaVar.resize(num);
        pointClouds_->SNRArray.resize(num);
    }

private: 
    std::shared_ptr<ThreeDimArray<ComplexFloat>> doppler_profile_;
    peakSearch_output_ peakOutput_;
    detectionCFAR_output_ cfar_output_;// get snr from cfar_output
    // pointClouds pointClouds_;
    std::shared_ptr<pointClouds> pointClouds_;
    RadarBasicConfig radar_basic_config_;
    // int fft_num;
    int n_samples_;
    int n_chirps_;
    int n_vrx_;

};

class DBFAngleEstimation: public DOAEstimation
{
public:
    DBFAngleEstimation(RadarBasicConfig &radar_basic_conf, std::shared_ptr<ThreeDimArray<ComplexFloat>> &doppler_profile) : radar_basic_config_(radar_basic_conf),DOAEstimation(radar_basic_conf,doppler_profile)
    {
        doppler_profile_ = doppler_profile;
        n_samples_ = radar_basic_conf.adcSamples;
        n_chirps_ = radar_basic_conf.numChirps;
        n_vrx_ = radar_basic_conf.numRx * radar_basic_conf.numTx;

        pointClouds_ =std::make_shared<pointClouds>();
        cfar_output_.RD_after_cfar.resize(n_samples_);
        peakOutput_.RD_peakSearch.resize(n_samples_);
        for (int i = 0; i < n_samples_; i++)
        {
            cfar_output_.RD_after_cfar[i].resize(n_chirps_);
            peakOutput_.RD_peakSearch[i].resize(n_chirps_);
        }
    };
    ~DBFAngleEstimation(){}
    void doa_estimation() override;

    std::shared_ptr<pointClouds>& getPCL() override{
        return pointClouds_;
    }

    phaseParameter setPhaseParameters(){
        phaseParameter phaseParam;
        phaseParam.dopplerBin = radar_basic_config_.numChirps;
        phaseParam.rxAntenna = radar_basic_config_.numRx;
        phaseParam.txAntenna = radar_basic_config_.numTx;
        phaseParam.virtualAntenna = phaseParam.rxAntenna*phaseParam.txAntenna;
        return phaseParam;

    }

    void setPeakSearchOutput(peakSearch_output_& peakOutput) override{
        peakOutput_ = peakOutput;
    }
    void setCfarOutput(detectionCFAR_output_& cfarOutput) override{
        cfar_output_ = cfarOutput;
    }
    std::vector<float> normComplexArray(ComplexFloat *ComplexArray, int len)
    {

        std::vector<float> result;
        for (int i = 0; i < len; i++)
        {
                float temp = sqrt(ComplexArray[i].imag() * ComplexArray[i].imag() + ComplexArray[i].real() * ComplexArray[i].real());
                result.push_back(temp);
        }

        return result;
    }
    void angleDBF(ComplexFloat *frameData, float &angle);
    void init(int num)
    {
        pointClouds_->num = num;
        pointClouds_->rangeIdxArray.resize(num);
        pointClouds_->rangeFloat.resize(num);
        pointClouds_->speedIdxArray.resize(num);
        pointClouds_->speedFloat.resize(num);
        pointClouds_->aoaVar.resize(num);
        pointClouds_->SNRArray.resize(num);
    }

private: 
    std::shared_ptr<ThreeDimArray<ComplexFloat>> doppler_profile_;
    peakSearch_output_ peakOutput_;
    detectionCFAR_output_ cfar_output_;// get snr from cfar_output
    // pointClouds pointClouds_;
    std::shared_ptr<pointClouds> pointClouds_;
    RadarBasicConfig radar_basic_config_;
    // int fft_num;
    int n_samples_;
    int n_chirps_;
    int n_vrx_;

};

class CaponAngleEstimation: public DOAEstimation
{
public:
    CaponAngleEstimation(RadarBasicConfig &radar_basic_conf, std::shared_ptr<ThreeDimArray<ComplexFloat>> &doppler_profile) : radar_basic_config_(radar_basic_conf),DOAEstimation(radar_basic_conf,doppler_profile)
    {
        doppler_profile_ = doppler_profile;
        n_samples_ = radar_basic_conf.adcSamples;
        n_chirps_ = radar_basic_conf.numChirps;
        n_vrx_ = radar_basic_conf.numRx * radar_basic_conf.numTx;

        pointClouds_ =std::make_shared<pointClouds>();
        cfar_output_.RD_after_cfar.resize(n_samples_);
        peakOutput_.RD_peakSearch.resize(n_samples_);
        for (int i = 0; i < n_samples_; i++)
        {
            cfar_output_.RD_after_cfar[i].resize(n_chirps_);
            peakOutput_.RD_peakSearch[i].resize(n_chirps_);
        }
    };
    ~CaponAngleEstimation(){}
    void doa_estimation() override;

    std::shared_ptr<pointClouds>& getPCL() override{
        return pointClouds_;
    }

    phaseParameter setPhaseParameters(){
        phaseParameter phaseParam;
        phaseParam.dopplerBin = radar_basic_config_.numChirps;
        phaseParam.rxAntenna = radar_basic_config_.numRx;
        phaseParam.txAntenna = radar_basic_config_.numTx;
        phaseParam.virtualAntenna = phaseParam.rxAntenna*phaseParam.txAntenna;
        return phaseParam;

    }

    void setPeakSearchOutput(peakSearch_output_& peakOutput) override{
        peakOutput_ = peakOutput;
    }
    void setCfarOutput(detectionCFAR_output_& cfarOutput) override{
        cfar_output_ = cfarOutput;
    }
    std::vector<float> normComplexArray(ComplexFloat *ComplexArray, int len)
    {

        std::vector<float> result;
        for (int i = 0; i < len; i++)
        {
                float temp = sqrt(ComplexArray[i].imag() * ComplexArray[i].imag() + ComplexArray[i].real() * ComplexArray[i].real());
                result.push_back(temp);
        }

        return result;
    }
    void angleCapon(ComplexFloat *frameData, float &angle);
    void init(int num)
    {
        pointClouds_->num = num;
        pointClouds_->rangeIdxArray.resize(num);
        pointClouds_->rangeFloat.resize(num);
        pointClouds_->speedIdxArray.resize(num);
        pointClouds_->speedFloat.resize(num);
        pointClouds_->aoaVar.resize(num);
        pointClouds_->SNRArray.resize(num);
    }

private: 
    std::shared_ptr<ThreeDimArray<ComplexFloat>> doppler_profile_;
    peakSearch_output_ peakOutput_;
    detectionCFAR_output_ cfar_output_;// get snr from cfar_output
    // pointClouds pointClouds_;
    std::shared_ptr<pointClouds> pointClouds_;
    RadarBasicConfig radar_basic_config_;
    // int fft_num;
    int n_samples_;
    int n_chirps_;
    int n_vrx_;

};


class MusicAngleEstimation: public DOAEstimation
{
public:
    MusicAngleEstimation(RadarBasicConfig &radar_basic_conf, std::shared_ptr<ThreeDimArray<ComplexFloat>> &doppler_profile) : radar_basic_config_(radar_basic_conf),DOAEstimation(radar_basic_conf,doppler_profile)
    {
        doppler_profile_ = doppler_profile;
        n_samples_ = radar_basic_conf.adcSamples;
        n_chirps_ = radar_basic_conf.numChirps;
        n_vrx_ = radar_basic_conf.numRx * radar_basic_conf.numTx;

        pointClouds_ =std::make_shared<pointClouds>();
        cfar_output_.RD_after_cfar.resize(n_samples_);
        peakOutput_.RD_peakSearch.resize(n_samples_);
        for (int i = 0; i < n_samples_; i++)
        {
            cfar_output_.RD_after_cfar[i].resize(n_chirps_);
            peakOutput_.RD_peakSearch[i].resize(n_chirps_);
        }
    };
    ~MusicAngleEstimation(){}
    void doa_estimation() override;

    std::shared_ptr<pointClouds>& getPCL() override{
        return pointClouds_;
    }

    phaseParameter setPhaseParameters(){
        phaseParameter phaseParam;
        phaseParam.dopplerBin = radar_basic_config_.numChirps;
        phaseParam.rxAntenna = radar_basic_config_.numRx;
        phaseParam.txAntenna = radar_basic_config_.numTx;
        phaseParam.virtualAntenna = phaseParam.rxAntenna*phaseParam.txAntenna;
        return phaseParam;

    }

    void setPeakSearchOutput(peakSearch_output_& peakOutput) override{
        peakOutput_ = peakOutput;
    }
    void setCfarOutput(detectionCFAR_output_& cfarOutput) override{
        cfar_output_ = cfarOutput;
    }
    std::vector<float> normComplexArray(ComplexFloat *ComplexArray, int len)
    {

        std::vector<float> result;
        for (int i = 0; i < len; i++)
        {
                float temp = sqrt(ComplexArray[i].imag() * ComplexArray[i].imag() + ComplexArray[i].real() * ComplexArray[i].real());
                result.push_back(temp);
        }

        return result;
    }
    void angleMusic(ComplexFloat *frameData, float &angle);
    void init(int num)
    {
        pointClouds_->num = num;
        pointClouds_->rangeIdxArray.resize(num);
        pointClouds_->rangeFloat.resize(num);
        pointClouds_->speedIdxArray.resize(num);
        pointClouds_->speedFloat.resize(num);
        pointClouds_->aoaVar.resize(num);
        pointClouds_->SNRArray.resize(num);
    }

private: 
    std::shared_ptr<ThreeDimArray<ComplexFloat>> doppler_profile_;
    peakSearch_output_ peakOutput_;
    detectionCFAR_output_ cfar_output_;// get snr from cfar_output
    // pointClouds pointClouds_;
    std::shared_ptr<pointClouds> pointClouds_;
    RadarBasicConfig radar_basic_config_;
    // int fft_num;
    int n_samples_;
    int n_chirps_;
    int n_vrx_;

};

class RadarDetection{
public:
    using Ptr = std::shared_ptr<RadarDetection>;

    RadarDetection(ThreeDimArray<ComplexFloat> radarcube, int frame_idx, int frame_size, RadarBasicConfig radar_basic_conf, RadarDetectionConfig radar_conf) : frame_id_(frame_idx), frame_size_(frame_size), m_n_samples_(radarcube.m_width), m_n_chirps_(radarcube.m_height), m_n_vrx_(radarcube.m_depth), radar_basic_config_(radar_basic_conf), radar_detection_config_(radar_conf)
    {

        radarDataPtr_ = std::make_shared<ThreeDimArray<ComplexFloat>>(radarcube);
        rangeProfilePtr = std::make_shared<ThreeDimArray<ComplexFloat>>(m_n_samples_, m_n_chirps_, m_n_vrx_);
        dopplerProfilePtr = std::make_shared<ThreeDimArray<ComplexFloat>>(m_n_samples_, m_n_chirps_, m_n_vrx_);
        RadarBeforeCfarPtr = std::make_shared<TwoDimArray<float>>(m_n_samples_, m_n_chirps_);
        cfar_output.RD_after_cfar.resize(m_n_samples_);
        peak_output.RD_peakSearch.resize(m_n_samples_);
        for (int i = 0; i < m_n_samples_; i++)
        {
            cfar_output.RD_after_cfar[i].resize(m_n_chirps_);
            peak_output.RD_peakSearch[i].resize(m_n_chirps_);
        }
        
    };
    ~RadarDetection(){};

    ComplexFloat getData(int i,int j,int k){
        return radarDataPtr_->at(i,j,k);
    };

    // range estimation
    void rangeEstimation();

    // doppler estimation
    void dopplerEstimation();

    void non_coherent_combing();

    void SetCfarInput(){
         cfar_detection->setCfarInput(RadarBeforeCfarPtr);
    }
    // cfar detection

    void cfarDetection();

    void peakGrouping();

    void runDetection();

    void doaEstimation();

    // pointClouds& getPCL(){
    //     return point_clouds;
    // }
    std::shared_ptr<pointClouds>& getPCL(){
        return point_clouds;
    }
  
private:
    int frame_id_;
    int frame_size_;
    int m_n_samples_;
    int m_n_chirps_;
    int m_n_vrx_;

    std::shared_ptr<ThreeDimArray<ComplexFloat>> radarDataPtr_;

    std::shared_ptr<ThreeDimArray<ComplexFloat>> rangeProfilePtr;
    std::shared_ptr<ThreeDimArray<ComplexFloat>> dopplerProfilePtr;
    std::shared_ptr<TwoDimArray<float>> RadarBeforeCfarPtr;
    RadarDetectionConfig radar_detection_config_;
    RadarBasicConfig radar_basic_config_;
    CfarDetection* cfar_detection;
    peakSearch_output_ peak_output;
    detectionCFAR_output_ cfar_output;
    // pointClouds point_clouds;
    std::shared_ptr<pointClouds> point_clouds;
    FFTAngleEstimation* fft_doa;
  
};

}   // namespace inference

}   // namespace ai

}   // namespace hce

#endif //#ifndef HCE_AI_INF_RADAR_DETECTION_HELPER_HPP
