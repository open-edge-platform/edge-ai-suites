// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_OPTIMIZE_G2O_SE3_SHOT_VERTEX_CONTAINER_H
#define OPENVSLAM_OPTIMIZE_G2O_SE3_SHOT_VERTEX_CONTAINER_H

#include "type.h"
#include "util/converter.h"
#include "data/frame.h"
#include "data/keyframe.h"
#include "optimize/g2o/se3/shot_vertex.h"

#include <unordered_map>

namespace openvslam {

namespace data {
class frame;
class keyframe;
}  // namespace data

namespace optimize {
namespace g2o {
namespace se3 {

class shot_vertex_container {
public:
    /**
     * Constructor
     * @param offset
     * @param num_reserve
     */
    explicit shot_vertex_container(const KeyframeID offset = 0, const unsigned int num_reserve = 50);

    /**
     * Destructor
     */
    virtual ~shot_vertex_container() = default;

    /**
     * Create and return the g2o vertex created from the specified frame
     * @param frm
     * @param is_constant
     * @return
     */
    shot_vertex* create_vertex(data::frame* frm, const bool is_constant)
    {
        return create_vertex(frm->id_, frm->cam_pose_cw_, is_constant);
    }

    /**
     * Create and return the g2o vertex created from the specified keyframe
     * @param keyfrm
     * @param is_constant
     * @return
     */
    shot_vertex* create_vertex(data::keyframe* keyfrm, const bool is_constant)
    {
        return create_vertex(keyfrm->id_, keyfrm->get_cam_pose(), is_constant);
    }

    /**
     * Create and return the g2o vertex created from shot ID and camera pose
     * @param id
     * @param cam_pose_cw
     * @param is_constant
     * @return
     */
    shot_vertex* create_vertex(const KeyframeID id, const Mat44_t& cam_pose_cw, const bool is_constant);

    /**
     * Get vertex corresponding with the specified frame
     * @param frm
     * @return
     */
    inline shot_vertex* get_vertex(data::frame* frm) const { return get_vertex(frm->id_); }

    /**
     * Get vertex corresponding with the specified keyframe
     * @param keyfrm
     * @return
     */
    inline shot_vertex* get_vertex(data::keyframe* keyfrm) const { return get_vertex(keyfrm->id_); }

    /**
     * Get vertex corresponding with the specified shot (frame/keyframe) ID
     * @param id
     * @return
     */
    inline shot_vertex* get_vertex(const KeyframeID id) const
    {
        if (vtx_container_.find(id) == vtx_container_.end()) return nullptr;
        return vtx_container_.at(id);
    }

    /**
     * Convert frame ID to vertex ID
     * @param frm
     * @return
     */
    inline int get_vertex_id(data::frame* frm) const { return get_vertex_id(frm->id_); }

    /**
     * Convert keyframe ID to vertex ID
     * @param keyfrm
     * @return
     */
    inline int get_vertex_id(data::keyframe* keyfrm) const { return get_vertex_id(keyfrm->id_); }

    /**
     * Convert shot (frame/keyframe) ID to vertex ID
     * @param id
     * @return
     */
    inline int get_vertex_id(const KeyframeID id) const
    {
        return keyframeID_to_vertexID(offset_ + id);
    }

    /**
     * Get maximum vertex ID
     * @return
     */
    inline int get_max_vertex_id() const { return max_vtx_id_; }

    /**
     * Contains the specified keyframe or not
     */
    inline bool contain(data::keyframe* keyfrm) const { return 0 != vtx_container_.count(keyfrm->id_); }

    typedef std::unordered_map<KeyframeID, shot_vertex*>::iterator iterator;
    typedef std::unordered_map<KeyframeID, shot_vertex*>::const_iterator const_iterator;

    iterator begin() { return vtx_container_.begin(); }
    const_iterator begin() const { return vtx_container_.begin(); }
    iterator end() { return vtx_container_.end(); }
    const_iterator end() const { return vtx_container_.end(); }

private:
    //! vertex ID = offset + shot (frame/keyframe) ID
    const KeyframeID offset_ = 0;

    //! key: shot (frame/keyframe) ID, value: vertex
    std::unordered_map<KeyframeID, shot_vertex*> vtx_container_;

    //! max vertex ID
    int max_vtx_id_ = 0;
};

}  // namespace se3
}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_OPTIMIZE_G2O_SE3_SHOT_VERTEX_CONTAINER_H
