// SPDX-License-Identifier: BSD-3-Clause
// SPDX-FileCopyrightText: (C) 2015 TRACLabs, Inc.
// Copyright (c) 2015, TRACLabs, Inc.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
//    * Redistributions of source code must retain the above copyright
//      notice, this list of conditions and the following disclaimer.
//
//    * Redistributions in binary form must reproduce the above copyright
//      notice, this list of conditions and the following disclaimer in the
//      documentation and/or other materials provided with the distribution.
//
//    * Neither the name of the {copyright_holder} nor the names of its
//      contributors may be used to endorse or promote products derived from
//      this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
// ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
// LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
// CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
// SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
// INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
// CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
// POSSIBILITY OF SUCH DAMAGE.


#ifndef TRAC_IK__TRAC_IK_HPP_
#define TRAC_IK__TRAC_IK_HPP_


#include <chrono>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include <utility>
#include <mutex>
#include <condition_variable>

#include "kdl/chainjnttojacsolver.hpp"
#include "trac_ik/nlopt_ik.hpp"
#include "trac_ik/visibility_control.hpp"


namespace TRAC_IK
{

enum SolveType { Speed, Distance, Manip1, Manip2 };

class TRAC_IK_PUBLIC TRAC_IK
{
public:
  TRAC_IK_PUBLIC
  TRAC_IK(
    const KDL::Chain & _chain, const KDL::JntArray & _q_min, const KDL::JntArray & _q_max,
    double _maxtime = 0.005, double _eps = 1e-5, SolveType _type = Speed);

  TRAC_IK_PUBLIC
  TRAC_IK(
    const std::string & base_link, const std::string & tip_link,
    const std::string & urdf_xml = "", double _maxtime = 0.005, double _eps = 1e-5,
    SolveType _type = Speed);

  TRAC_IK_PUBLIC
  ~TRAC_IK();

  TRAC_IK_PUBLIC
  bool getKDLChain(KDL::Chain & chain_)
  {
    chain_ = chain;
    return initialized;
  }

  TRAC_IK_PUBLIC
  bool getKDLLimits(KDL::JntArray & lb_, KDL::JntArray & ub_)
  {
    lb_ = lb;
    ub_ = ub;
    return initialized;
  }

  TRAC_IK_PUBLIC
  // Requires a previous call to CartToJnt()
  bool getSolutions(std::vector<KDL::JntArray> & solutions_)
  {
    solutions_ = solutions;
    return initialized && !solutions.empty();
  }

  TRAC_IK_PUBLIC
  bool getSolutions(
    std::vector<KDL::JntArray> & solutions_, std::vector<std::pair<double,
    uint>> & errors_)
  {
    errors_ = errors;
    return getSolutions(solutions_);
  }

  TRAC_IK_PUBLIC
  bool setKDLLimits(KDL::JntArray & lb_, KDL::JntArray & ub_)
  {
    lb = lb_;
    ub = ub_;
    nl_solver.reset(new NLOPT_IK::NLOPT_IK(chain, lb, ub, maxtime.count(), eps, NLOPT_IK::SumSq));
    iksolver.reset(new KDL::ChainIkSolverPos_TL(chain, lb, ub, maxtime.count(), eps, true, true));
    return true;
  }

  TRAC_IK_PUBLIC
  static double JointErr(const KDL::JntArray & arr1, const KDL::JntArray & arr2)
  {
    double err = 0;
    for (uint i = 0; i < arr1.data.size(); i++) {
      err += pow(arr1(i) - arr2(i), 2);
    }

    return err;
  }

  TRAC_IK_PUBLIC
  int CartToJnt(
    const KDL::JntArray & q_init, const KDL::Frame & p_in, KDL::JntArray & q_out, 
    const std::chrono::time_point<std::chrono::steady_clock, std::chrono::duration<double>> start_time_arg,
    const KDL::Twist & bounds = KDL::Twist::Zero());

  inline void SetSolveType(SolveType _type)
  {
    solvetype = _type;
  }

  inline SolveType GetSolveType() const
  {
    return solvetype;
  }

private:
  KDL::JntArray q_init;

  KDL::Frame p_in_arg;
  std::mutex mutexWorkers, mutexMain;
  std::condition_variable conditionWorkers,conditionMain;
  bool notifyFlag;
  
  bool initialized;
  KDL::Chain chain;
  KDL::JntArray lb, ub;
  std::unique_ptr<KDL::ChainJntToJacSolver> jacsolver;
  double eps;
  std::chrono::duration<double> maxtime;
  SolveType solvetype;

  std::unique_ptr<NLOPT_IK::NLOPT_IK> nl_solver;
  std::unique_ptr<KDL::ChainIkSolverPos_TL> iksolver;

  std::chrono::time_point<std::chrono::steady_clock, std::chrono::duration<double>> start_time;

  template<typename T1, typename T2>
  bool runSolver(
    T1 & solver, T2 & other_solver);

  bool runKDL();
  bool runNLOPT();

  void normalize_seed(const KDL::JntArray & seed, KDL::JntArray & solution);
  void normalize_limits(const KDL::JntArray & seed, KDL::JntArray & solution);

  std::vector<KDL::BasicJointType> types;

  std::mutex mtx_;
  std::vector<KDL::JntArray> solutions;
  std::vector<std::pair<double, uint>> errors;

  std::thread task1, task2;
  KDL::Twist bounds;

  bool unique_solution(const KDL::JntArray & sol);

  inline static double fRand(double min, double max)
  {
    double f = static_cast<double>(rand()) / RAND_MAX;  // NOLINT
    return min + f * (max - min);
  }

  /* @brief Manipulation metrics and penalties taken from "Workspace
  Geometric Characterization and Manipulability of Industrial Robots",
  Ming-June, Tsia, PhD Thesis, Ohio State University, 1986.
  https://etd.ohiolink.edu/!etd.send_file?accession=osu1260297835
  */
  double manipPenalty(const KDL::JntArray &);
  double ManipValue1(const KDL::JntArray &);
  double ManipValue2(const KDL::JntArray &);

  inline bool myEqual(const KDL::JntArray & a, const KDL::JntArray & b)
  {
    return (a.data - b.data).isZero(1e-4);
  }

  void initialize();
};

inline bool TRAC_IK::runKDL()
{
  cpu_set_t cpuset;
  CPU_ZERO(&cpuset);
  CPU_SET(2, &cpuset);
  pthread_setaffinity_np(pthread_self(), sizeof(cpu_set_t), &cpuset);    
  
  struct sched_param params;
  params.sched_priority = 99;
   pthread_setschedparam ( pthread_self(), SCHED_FIFO, &params );
  pthread_setname_np ( pthread_self(), "KDL" );

  return runSolver(*iksolver.get(), *nl_solver.get());
}

inline bool TRAC_IK::runNLOPT()
{
  cpu_set_t cpuset;
  CPU_ZERO(&cpuset);
  CPU_SET(4, &cpuset);
  pthread_setaffinity_np(pthread_self(), sizeof(cpu_set_t), &cpuset);    
  
    
  struct sched_param params;
  params.sched_priority = 99;
   pthread_setschedparam ( pthread_self(), SCHED_FIFO, &params );
  pthread_setname_np ( pthread_self(), "NL" );

  return runSolver(*nl_solver.get(), *iksolver.get());
}

}  // namespace TRAC_IK

#endif  // TRAC_IK__TRAC_IK_HPP_
