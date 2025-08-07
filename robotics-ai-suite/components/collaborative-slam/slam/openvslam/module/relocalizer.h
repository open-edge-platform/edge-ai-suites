// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_MODULE_RELOCALIZER_H
#define OPENVSLAM_MODULE_RELOCALIZER_H
#include "match/robust.h"
#include "match/bow_tree.h"
#include "match/projection.h"
#include "optimize/pose_optimizer.h"
#include "solve/pnp_solver.h"
#include "data/bow_vocabulary.h"

namespace openvslam {

namespace data {
class frame;
class bow_database;
}  // namespace data

namespace camera {
enum class setup_type_t;
}

namespace module {

class relocalizer {
public:
    //! Constructor
    explicit relocalizer(data::bow_database* bow_db, camera::setup_type_t camera_type, const double bow_match_lowe_ratio = 0.75,
                         const double proj_match_lowe_ratio = 0.9, const unsigned int min_num_bow_matches = 20,
                         const unsigned int min_num_valid_obs = 50);

    //! Destructor
    virtual ~relocalizer();

    //! Relocalize the specified frame
    bool relocalize(data::frame& curr_frm);
    bool relocalize(data::frame& curr_frm, MapID& map_id, data::map_database* map_db, data::bow_vocabulary* bow_vocab,
                    double near_distance, double far_distance, double back_distance);

    void set_camera_type(camera::setup_type_t camera_type);

private:
    // get virtual keyframe according to covisibility_keyframes' landmark
    std::shared_ptr<data::keyframe> get_covisibility_keyfrm(data::keyframe* keyfrm, data::map_database* map_db,
                                                            data::bow_vocabulary* bow_vocab, int top_number);

    // get virtual keyframe according to reprojecttion landmark
    std::shared_ptr<data::keyframe> get_projection_keyfrm(data::keyframe* keyfrm, data::map_database* map_db,
                                                          data::bow_vocabulary* bow_vocab, double near_distance,
                                                          double far_distance, double back_distance);

    // get virtual keyfrms according to landmarks
    std::shared_ptr<data::keyframe> get_virtual_keyfrm(data::keyframe* keyfrm, data::map_database* map_db,
                                                       data::bow_vocabulary* bow_vocab,
                                                       std::vector<data::landmark*>& nearby_landmarks);
    //! Extract valid (non-deleted) landmarks from landmark vector
    std::vector<unsigned int> extract_valid_indices(const std::vector<data::landmark*>& landmarks) const;

    //! Setup PnP solver with the specified 2D-3D matches
    std::unique_ptr<solve::pnp_solver> setup_pnp_solver(const std::vector<unsigned int>& valid_indices,
                                                        const eigen_alloc_vector<Vec3_t>& bearings,
                                                        const std::vector<cv::KeyPoint>& keypts,
                                                        const std::vector<data::landmark*>& matched_landmarks,
                                                        const std::vector<float>& scale_factors) const;

    //! BoW database
    data::bow_database* bow_db_;

    //! minimum threshold of the number of BoW matches
    const unsigned int min_num_bow_matches_;
    //! minimum threshold of the number of valid (= inlier after pose optimization) matches
    const unsigned int min_num_valid_obs_;

    //! BoW matcher
    const match::bow_tree bow_matcher_;
    //! projection matcher
    const match::projection proj_matcher_;
    //! pose optimizer
    optimize::pose_optimizer pose_optimizer_;
};

}  // namespace module
}  // namespace openvslam

#endif  // OPENVSLAM_MODULE_RELOCALIZER_H
