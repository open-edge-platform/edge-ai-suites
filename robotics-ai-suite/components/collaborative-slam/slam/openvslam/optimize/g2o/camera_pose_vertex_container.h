// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef CAMERA_POSE_VERTEX_CONTAINER_H
#define CAMERA_POSE_VERTEX_CONTAINER_H

#include "type.h"
#include "util/converter.h"
#include "camera_pose_vertex.h"
#include "data/keyframe.h"
#include <unordered_map>

namespace openvslam {

namespace optimize {
namespace g2o {

class camera_pose_vertex_container {
public:
    /**
     * Constructor
     * @param offset
     * @param num_reserve
     */
    explicit camera_pose_vertex_container(const KeyframeID offset, const unsigned int num_reserve = 200);

    /**
     * Destructor
     */
    virtual ~camera_pose_vertex_container() = default;

    /**
     * Create and return the g2o vertex created from the specified landmark
     * @param id
     * @param pos_w
     * @param is_constant
     * @return
     */
    camera_pose_vertex* create_vertex(const KeyframeID id, const Mat44_t T, const bool is_constant);

    /**
     * Get vertex corresponding with the specified landmark ID
     * @param id
     * @return
     */
    inline camera_pose_vertex* get_vertex(const KeyframeID id) const { return vtx_container_.at(id); }

    camera_pose_vertex* create_vertex(data::keyframe* keyfrm, const bool is_constant)
    {
        return create_vertex(keyfrm->id_, keyfrm->get_cam_pose(), is_constant);
    }

    /**
     * Convert landmark ID to vertex ID
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
    int get_max_vertex_id() const { return max_vtx_id_; }

    /**
     * Get vertex corresponding with the specified keyframe
     * @param keyfrm
     * @return
     */
    inline camera_pose_vertex* get_vertex(data::keyframe* keyfrm) const { return get_vertex(keyfrm->id_); }

    typedef std::unordered_map<KeyframeID, camera_pose_vertex*>::iterator iterator;
    typedef std::unordered_map<KeyframeID, camera_pose_vertex*>::const_iterator const_iterator;

    iterator begin() { return vtx_container_.begin(); }
    const_iterator begin() const { return vtx_container_.begin(); }
    iterator end() { return vtx_container_.end(); }
    const_iterator end() const { return vtx_container_.end(); }

private:
    //! vertex ID = offset + landmark ID
    const KeyframeID offset_ = 0;

    //! key: landmark ID, value: vertex
    std::unordered_map<KeyframeID, camera_pose_vertex*> vtx_container_;

    //! max vertex ID
    int max_vtx_id_ = 0;
};

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

#endif
