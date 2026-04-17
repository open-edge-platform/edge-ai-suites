// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "optimize/graph_optimizer.h"
#include "optimize/g2o/sim3/shot_vertex.h"
#include "optimize/g2o/sim3/graph_opt_edge.h"
#include "util/converter.h"

#include <Eigen/StdVector>
#include <g2o/core/solver.h>
#include <g2o/core/block_solver.h>
#include <g2o/core/sparse_optimizer.h>
#include <g2o/core/robust_kernel_impl.h>
#include <g2o/solvers/csparse/linear_solver_csparse.h>
#include <g2o/core/optimization_algorithm_levenberg.h>

namespace openvslam
{
namespace optimize
{

graph_optimizer::graph_optimizer(data::map_database * map_db, const bool fix_scale)
: map_db_(map_db), fix_scale_(fix_scale)
{
}

void graph_optimizer::optimize(
  data::keyframe * loop_keyfrm, data::keyframe * curr_keyfrm,
  const module::keyframe_Sim3_pairs_t & non_corrected_Sim3s,
  const module::keyframe_Sim3_pairs_t & pre_corrected_Sim3s,
  const std::map<data::keyframe *, std::set<data::keyframe *>> & loop_connections) const
{
  // 1. optimizer

  auto linear_solver =
    ::std::make_unique<::g2o::LinearSolverCSparse<::g2o::BlockSolver_7_3::PoseMatrixType>>();
  auto block_solver = ::std::make_unique<::g2o::BlockSolver_7_3>(std::move(linear_solver));
  auto algorithm = new ::g2o::OptimizationAlgorithmLevenberg(std::move(block_solver));

  ::g2o::SparseOptimizer optimizer;
  optimizer.setAlgorithm(algorithm);

  // 2. vertex

  const auto all_keyfrms = map_db_->get_all_keyframes();
  const auto all_lms = map_db_->get_all_landmarks();

  const KeyframeID max_keyfrm_id = map_db_->get_max_keyframe_id();

  std::vector<::g2o::Sim3, Eigen::aligned_allocator<::g2o::Sim3>> Sim3s_cw(max_keyfrm_id + 1);
  std::vector<g2o::sim3::shot_vertex *> vertices(max_keyfrm_id + 1);

  constexpr int min_weight = 100;

  for (auto keyfrm : all_keyfrms) {
    if (keyfrm->will_be_erased()) {
      continue;
    }
    auto keyfrm_vtx = new g2o::sim3::shot_vertex();

    const auto id = keyfrm->id_;

    const auto iter = pre_corrected_Sim3s.find(keyfrm);
    if (iter != pre_corrected_Sim3s.end()) {
      Sim3s_cw.at(id) = iter->second;
      keyfrm_vtx->setEstimate(iter->second);
    } else {
      const Mat33_t rot_cw = keyfrm->get_rotation();
      const Vec3_t trans_cw = keyfrm->get_translation();
      const ::g2o::Sim3 Sim3_cw(rot_cw, trans_cw, 1.0);

      Sim3s_cw.at(id) = Sim3_cw;
      keyfrm_vtx->setEstimate(Sim3_cw);
    }

    if (*keyfrm == *loop_keyfrm) {
      keyfrm_vtx->setFixed(true);
    }

    // vertex optimizer
    keyfrm_vtx->setId(keyframeID_to_vertexID(id));
    keyfrm_vtx->fix_scale_ = fix_scale_;

    optimizer.addVertex(keyfrm_vtx);
    vertices.at(id) = keyfrm_vtx;
  }

  // 3. edge

  std::set<std::pair<KeyframeID, KeyframeID>> inserted_edge_pairs;

  // constraint edge
  const auto insert_edge = [&optimizer, &vertices, &inserted_edge_pairs](
                             KeyframeID id1, KeyframeID id2, const ::g2o::Sim3 & Sim3_21) {
    auto edge = new g2o::sim3::graph_opt_edge();
    edge->setVertex(0, vertices.at(id1));
    edge->setVertex(1, vertices.at(id2));
    edge->setMeasurement(Sim3_21);

    edge->information() = MatRC_t<7, 7>::Identity();

    optimizer.addEdge(edge);
    inserted_edge_pairs.insert(std::make_pair(std::min(id1, id2), std::max(id1, id2)));
  };

  // threshold weight loop edge
  for (const auto & loop_connection : loop_connections) {
    auto keyfrm = loop_connection.first;
    const auto & connected_keyfrms = loop_connection.second;

    const auto id1 = keyfrm->id_;
    const ::g2o::Sim3 & Sim3_1w = Sim3s_cw.at(id1);
    const ::g2o::Sim3 Sim3_w1 = Sim3_1w.inverse();

    for (const auto & connected_keyfrm : connected_keyfrms) {
      const auto id2 = connected_keyfrm->id_;

      // current vs loop edge，weight threshold
      if (
        (id1 != curr_keyfrm->id_ || id2 != loop_keyfrm->id_) &&
        keyfrm->graph_node_->get_weight(connected_keyfrm) < min_weight) {
        continue;
      }

      const ::g2o::Sim3 & Sim3_2w = Sim3s_cw.at(id2);
      const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;

      // constraint edge
      insert_edge(id1, id2, Sim3_21);
    }
  }

  // loop connection edge
  for (const auto & keyfrm : all_keyfrms) {
    const auto id1 = keyfrm->id_;

    // covisibilities
    const auto iter1 = non_corrected_Sim3s.find(keyfrm);
    const ::g2o::Sim3 Sim3_w1 =
      ((iter1 != non_corrected_Sim3s.end()) ? iter1->second : Sim3s_cw.at(id1)).inverse();

    auto parent_node = keyfrm->graph_node_->get_spanning_parent();
    if (parent_node) {
      const auto id2 = parent_node->id_;

      if (id1 <= id2) {
        continue;
      }

      // covisibilities
      const auto iter2 = non_corrected_Sim3s.find(parent_node);
      const ::g2o::Sim3 & Sim3_2w =
        (iter2 != non_corrected_Sim3s.end()) ? iter2->second : Sim3s_cw.at(id2);

      const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;

      // constraint edge
      insert_edge(id1, id2, Sim3_21);
    }

    // loop edge weight
    const auto loop_edges = keyfrm->graph_node_->get_loop_edges();
    for (const auto & connected_keyfrm : loop_edges) {
      const auto id2 = connected_keyfrm->id_;

      if (id1 <= id2) {
        continue;
      }

      // covisibilities
      const auto iter2 = non_corrected_Sim3s.find(connected_keyfrm);
      const ::g2o::Sim3 & Sim3_2w =
        (iter2 != non_corrected_Sim3s.end()) ? iter2->second : Sim3s_cw.at(id2);

      const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;

      // constraint edge
      insert_edge(id1, id2, Sim3_21);
    }

    // threshold weight covisibilities
    const auto connected_keyfrms = keyfrm->graph_node_->get_covisibilities_over_weight(min_weight);
    for (const auto & connected_keyfrm : connected_keyfrms) {
      // null check
      if (!connected_keyfrm || !parent_node) {
        continue;
      }
      // parent-child edge
      if (
        *connected_keyfrm == *parent_node ||
        keyfrm->graph_node_->has_spanning_child(connected_keyfrm)) {
        continue;
      }
      // loop
      if (static_cast<bool>(loop_edges.count(connected_keyfrm))) {
        continue;
      }

      if (connected_keyfrm->will_be_erased()) {
        continue;
      }

      const auto id2 = connected_keyfrm->id_;

      if (id1 <= id2) {
        continue;
      }
      if (static_cast<bool>(
            inserted_edge_pairs.count(std::make_pair(std::min(id1, id2), std::max(id1, id2))))) {
        continue;
      }

      // covisibilities
      const auto iter2 = non_corrected_Sim3s.find(connected_keyfrm);
      const ::g2o::Sim3 & Sim3_2w =
        (iter2 != non_corrected_Sim3s.end()) ? iter2->second : Sim3s_cw.at(id2);

      const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;

      // constraint edge
      insert_edge(id1, id2, Sim3_21);
    }
  }

  // 4. pose graph optimization

  optimizer.initializeOptimization();
  optimizer.optimize(50);

  // 5.

  {
    std::lock_guard<std::mutex> lock(data::map_database::mtx_database_);

    std::vector<::g2o::Sim3, Eigen::aligned_allocator<::g2o::Sim3>> corrected_Sim3s_wc(
      max_keyfrm_id + 1);

    for (auto keyfrm : all_keyfrms) {
      const auto id = keyfrm->id_;

      auto keyfrm_vtx =
        static_cast<g2o::sim3::shot_vertex *>(optimizer.vertex(keyframeID_to_vertexID(id)));

      const ::g2o::Sim3 & corrected_Sim3_cw = keyfrm_vtx->estimate();
      const float s = corrected_Sim3_cw.scale();
      const Mat33_t rot_cw = corrected_Sim3_cw.rotation().toRotationMatrix();
      const Vec3_t trans_cw = corrected_Sim3_cw.translation() / s;

      const Mat44_t cam_pose_cw = util::converter::to_eigen_cam_pose(rot_cw, trans_cw);
      keyfrm->set_cam_pose(cam_pose_cw);

      corrected_Sim3s_wc.at(id) = corrected_Sim3_cw.inverse();
    }

    for (auto lm : all_lms) {
      if (lm->will_be_erased()) {
        continue;
      }

      const auto id = (lm->loop_fusion_identifier_ == curr_keyfrm->id_)
                        ? lm->ref_keyfrm_id_in_loop_fusion_
                        : lm->get_ref_keyframe()->id_;

      const ::g2o::Sim3 & Sim3_cw = Sim3s_cw.at(id);
      const ::g2o::Sim3 & corrected_Sim3_wc = corrected_Sim3s_wc.at(id);

      const Vec3_t pos_w = lm->get_pos_in_world();
      const Vec3_t corrected_pos_w = corrected_Sim3_wc.map(Sim3_cw.map(pos_w));

      lm->set_pos_in_world(corrected_pos_w);
      lm->update_normal_and_depth();
    }
  }
}

}  // namespace optimize
}  // namespace openvslam
