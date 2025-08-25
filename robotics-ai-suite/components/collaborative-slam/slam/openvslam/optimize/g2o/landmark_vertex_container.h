// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_OPTIMIZE_G2O_LANDMARK_VERTEX_CONTAINER_H
#define OPENVSLAM_OPTIMIZE_G2O_LANDMARK_VERTEX_CONTAINER_H

#include "type.h"
#include "util/converter.h"
#include "data/landmark.h"
#include "optimize/g2o/landmark_vertex.h"

#include <unordered_map>

namespace openvslam {

namespace data {
class landmark;
}  // namespace data

namespace optimize {
namespace g2o {

class landmark_vertex_container {
public:
    /**
     * Constructor
     * @param offset
     * @param num_reserve
     */
    explicit landmark_vertex_container(const LandmarkID offset, const unsigned int num_reserve = 200);

    /**
     * Destructor
     */
    virtual ~landmark_vertex_container() = default;

    /**
     * Create and return the g2o vertex created from the specified landmark
     * @param lm
     * @param is_constant
     * @return
     */
    landmark_vertex* create_vertex(data::landmark* lm, const bool is_constant)
    {
        return create_vertex(lm->id_, lm->get_pos_in_world(), is_constant);
    }

    /**
     * Create and return the g2o vertex created from the specified landmark
     * @param id
     * @param pos_w
     * @param is_constant
     * @return
     */
    landmark_vertex* create_vertex(const LandmarkID id, const Vec3_t& pos_w, const bool is_constant);

    /**
     * Get vertex corresponding with the specified landmark
     * @param lm
     * @return
     */
    inline landmark_vertex* get_vertex(data::landmark* lm) const { return get_vertex(lm->id_); }

    /**
     * Get vertex corresponding with the specified landmark ID
     * @param id
     * @return
     */
    inline landmark_vertex* get_vertex(const LandmarkID id) const { return vtx_container_.at(id); }

    /**
     * Convert landmark to vertex ID
     * @param lm
     * @return
     */
    inline int get_vertex_id(data::landmark* lm) const { return get_vertex_id(lm->id_); }

    /**
     * Convert landmark ID to vertex ID
     * @param id
     * @return
     */
    inline int get_vertex_id(const LandmarkID id) const
    {
        return landmarkID_to_vertexID(offset_ + id);
    }

    /**
     * Contains the specified landmark or not
     */
    inline bool contain(data::landmark* lm) const { return 0 != vtx_container_.count(lm->id_); }

    /**
     * Get maximum vertex ID
     * @return
     */
    int get_max_vertex_id() const { return max_vtx_id_; }

    typedef std::unordered_map<LandmarkID, landmark_vertex*>::iterator iterator;
    typedef std::unordered_map<LandmarkID, landmark_vertex*>::const_iterator const_iterator;

    iterator begin() { return vtx_container_.begin(); }
    const_iterator begin() const { return vtx_container_.begin(); }
    iterator end() { return vtx_container_.end(); }
    const_iterator end() const { return vtx_container_.end(); }

private:
    //! vertex ID = offset + landmark ID
    const LandmarkID offset_ = 0;

    //! key: landmark ID, value: vertex
    std::unordered_map<LandmarkID, landmark_vertex*> vtx_container_;

    //! max vertex ID
    int max_vtx_id_ = 0;
};

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_OPTIMIZE_G2O_LANDMARK_VERTEX_CONTAINER_H
