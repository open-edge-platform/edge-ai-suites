// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_OPTIMIZER_G2O_IMUBIAS_VERTEX_CONTAINER_H
#define OPENVSLAM_OPTIMIZER_G2O_IMUBIAS_VERTEX_CONTAINER_H

#include "type.h"
#include "util/converter.h"
#include "optimize/g2o/imubias_vertex.h"

#include <unordered_map>

namespace openvslam {

namespace optimize {
namespace g2o {

class imubias_vertex_container {
public:
    /**
     * Constructor
     * @param offset
     * @param num_reserve
     */
    explicit imubias_vertex_container(const LandmarkID offset, const unsigned int num_reserve = 200);

    /**
     * Destructor
     */
    virtual ~imubias_vertex_container() = default;

    /**
     * Create and return the g2o vertex created from the specified landmark
     * @param id
     * @param pos_w
     * @param is_constant
     * @return
     */
    imubias_vertex* create_vertex(const LandmarkID id, const Vec6_t vec6, const bool is_constant);

    /**
     * Get vertex corresponding with the specified landmark ID
     * @param id
     * @return
     */
    inline imubias_vertex* get_vertex(const LandmarkID id) const { return vtx_container_.at(id); }

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
     * Get maximum vertex ID
     * @return
     */
    int get_max_vertex_id() const { return max_vtx_id_; }

    typedef std::unordered_map<LandmarkID, imubias_vertex*>::iterator iterator;
    typedef std::unordered_map<LandmarkID, imubias_vertex*>::const_iterator const_iterator;

    iterator begin() { return vtx_container_.begin(); }
    const_iterator begin() const { return vtx_container_.begin(); }
    iterator end() { return vtx_container_.end(); }
    const_iterator end() const { return vtx_container_.end(); }

private:
    //! vertex ID = offset + landmark ID
    const LandmarkID offset_ = 0;

    //! key: landmark ID, value: vertex
    std::unordered_map<LandmarkID, imubias_vertex*> vtx_container_;

    //! max vertex ID
    int max_vtx_id_ = 0;
};

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

#endif
