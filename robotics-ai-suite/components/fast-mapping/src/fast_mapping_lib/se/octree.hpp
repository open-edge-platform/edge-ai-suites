/*

Copyright 2016 Emanuele Vespa, Imperial College London

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation
and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
may be used to endorse or promote products derived from this software without
specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

*/

#ifndef OCTREE_H
#define OCTREE_H

#include <algorithm>
#include <cstring>
#include <queue>
#include <tuple>
#include <vector>

#include "node.hpp"
#include "octree_defines.h"
#include "octant_ops.hpp"
#include "voxel_traits.hpp"
#include "algorithms/unique.hpp"
#include "utils/morton_utils.hpp"
#include "utils/memory_pool.hpp"
#include "utils/math_utils.h"

inline int __float_as_int(float value)
{
    union float_as_int {
        float f;
        int i;
    };

    float_as_int u;
    u.f = value;
    return u.i;
}

inline float __int_as_float(int value)
{
    union int_as_float {
        int i;
        float f;
    };

    int_as_float u;
    u.i = value;
    return u.f;
}

namespace se {

template <typename T>
class ray_iterator;

template <typename T>
class node_iterator;

template <typename T>
struct LeafNode {
    typedef voxel_traits<T> traits_type;
    typedef typename traits_type::value_type value_type;

    Eigen::Vector3i coordinates;
    int level;
    value_type data;

    LeafNode(Eigen::Vector3i coord, int level, value_type data) : coordinates(coord), level(level), data(data) {}
};

template <typename T>
class Octree {
public:
    typedef voxel_traits<T> traits_type;
    typedef typename traits_type::value_type value_type;
    value_type empty() const { return traits_type::empty(); }
    value_type init_val() const { return traits_type::initValue(); }

    // Compile-time constant expressions
    // # of voxels per side in a voxel block
    static constexpr unsigned int blockSide = BLOCK_SIDE;
    // maximum tree depth in bits
    static constexpr unsigned int max_depth = ((sizeof(key_t) * 8) / 3);
    // Tree depth at which blocks are found
    static constexpr unsigned int block_depth = max_depth - math::log2_const(BLOCK_SIDE);

    Octree(){};

    Octree(const Octree& octree);

    Octree& operator+=(const Octree& octree);

    ~Octree() { clear(); }

    /*! \brief Initialises the octree attributes
     * \param size number of voxels per side of the cube
     * \param dim cube extension per side, in meter
     */
    void init(int size, float dim);
    Eigen::Vector3f expand(Eigen::Vector3i directions);
    void clear();

    inline int size() const { return size_; }
    inline int init_size() const { return init_size_; }
    inline float dim() const { return dim_; }
    inline int max_node_level() const { return leaves_level_; }
    inline Node<T>* root() const { return root_; }

    /*! \brief Retrieves voxel value at coordinates (x,y,z), if not present it
     * allocates it. This method is not thread safe.
     * \param x x coordinate in interval [0, size]
     * \param y y coordinate in interval [0, size]
     * \param z z coordinate in interval [0, size]
     */
    void set(const int x, const int y, const int z, const value_type val);

    /*! \brief Retrieves voxel value at coordinates (x,y,z)
     * \param x x coordinate in interval [0, size]
     * \param y y coordinate in interval [0, size]
     * \param z z coordinate in interval [0, size]
     */
    value_type get(const int x, const int y, const int z) const;
    value_type get_fine(const int x, const int y, const int z) const;

    /*! \brief Fetch the voxel block at which contains voxel  (x,y,z)
     * \param x x coordinate in interval [0, size]
     * \param y y coordinate in interval [0, size]
     * \param z z coordinate in interval [0, size]
     */
    VoxelBlock<T>* fetch(const int x, const int y, const int z) const;

    /*! \brief Fetch the octant (x,y,z) at level depth
     * \param x x coordinate in interval [0, size]
     * \param y y coordinate in interval [0, size]
     * \param z z coordinate in interval [0, size]
     * \param depth maximum depth to be searched
     */
    Node<T>* fetch_octant(const int x, const int y, const int z, const int depth) const;

    /*! \brief Insert the octant at (x,y,z). Not thread safe.
     * \param x x coordinate in interval [0, size]
     * \param y y coordinate in interval [0, size]
     * \param z z coordinate in interval [0, size]
     * \param depth target insertion level
     */
    Node<T>* insert(const int x, const int y, const int z, const int depth, const int pose);

    /*! \brief Insert the octant (x,y,z) at maximum resolution. Not thread safe.
     * \param x x coordinate in interval [0, size]
     * \param y y coordinate in interval [0, size]
     * \param z z coordinate in interval [0, size]
     */
    VoxelBlock<T>* insert(const int x, const int y, const int z, const int pose);

    /*! \brief Interp voxel value at voxel position  (x,y,z)
     * \param pos three-dimensional coordinates in which each component belongs
     * to the interval [0, size]
     * \return signed distance function value at voxel position (x, y, z)
     */

    template <typename FieldSelect>
    float interp(const Eigen::Vector3f& pos, FieldSelect f) const;

    /*! \brief Compute the gradient at voxel position  (x,y,z)
     * \param pos three-dimensional coordinates in which each component belongs
     * to the interval [0, size]
     * \return gradient at voxel position pos
     */
    Eigen::Vector3f grad(const Eigen::Vector3f& pos) const;

    template <typename FieldSelect>
    Eigen::Vector3f grad(const Eigen::Vector3f& pos, FieldSelect selector) const;

    /*! \brief Get the list of allocated block. If the active switch is set to
     * true then only the visible blocks are retrieved.
     * \param blocklist output vector of allocated blocks
     * \param active boolean switch. Set to true to retrieve visible, allocated
     * blocks, false to retrieve all allocated blocks.
     */
    void getBlockList(std::vector<VoxelBlock<T>*>& blocklist, bool active);

    /*! \brief Get the list of non-block leaf nodes. A functor should be given
     * to filter the data.
     */
    template <typename Functor>
    void getLeafNodeList(std::vector<LeafNode<T> >& nodelist, Functor data_filter)
    {
        for (unsigned int i = 0; i < nodes_buffer_.size(); ++i) {
            Node<T>& node = *nodes_buffer_[i];
            int level = keyops::level(node.code_);
            for (unsigned int c = 0; c < 8; ++c) {
                if (node.child(c)) continue;
                if (!data_filter(node.value_[c])) continue;
                key_t child_key = keyops::child(node.code_, c, max_level_);
                nodelist.emplace_back(keyops::decode(child_key), level + 1, node.value_[c]);
            }
        }
    }

    MemoryPool<VoxelBlock<T> >& getBlockBuffer() { return block_buffer_; };
    MemoryPool<Node<T> >& getNodesBuffer() { return nodes_buffer_; };

    /*! \brief Computes the morton code of the block containing voxel
     * at coordinates (x,y,z)
     * \param x x coordinate in interval [0, size]
     * \param y y coordinate in interval [0, size]
     * \param z z coordinate in interval [0, size]
     */
    key_t hash(const int x, const int y, const int z)
    {
        const int scale = max_level_ - math::log2_const(blockSide);  // depth of blocks
        return keyops::encode(x, y, z, scale, max_level_);
    }

    key_t hash(const int x, const int y, const int z, key_t scale)
    {
        return keyops::encode(x, y, z, scale, max_level_);
    }

    /*! \brief allocate a set of voxel blocks via their positional key
     * \param keys collection of voxel block keys to be allocated (i.e. their
     * morton number)
     * \param number of keys in the keys array
     */
    bool allocate(key_t* keys, int num_elem, int pose);

    /*! \brief  save the origin position of the volume cube */
    void setOriginPosition(const Eigen::Vector3f& pos);
    const Eigen::Vector3f getOrigin() const;


	/*! \brief wrapper function to integrate world points into the octree */
	void allocate_points(const std::vector<Eigen::Vector3f>& world_points, const Eigen::Matrix4f& pose, const float zmin, const float zmax, const float band, const int pose_id);

    void save(const std::string& filename);
    void load(const std::string& filename);

    /*! \brief Counts the number of blocks allocated
     * \return number of voxel blocks allocated
     */
    int leavesCount();

    /*! \brief Counts the number of internal nodes
     * \return number of internal nodes
     */
    int nodeCount();

    void printMemStats(){
        // memory.printStats();
    };

private:
    Node<T>* root_;
    int size_ = 0;
    int init_size_ = 0;
    float dim_ = 0;
    int max_level_ = 0;
    int leaves_level_ = 0;
    MemoryPool<VoxelBlock<T> > block_buffer_;
    MemoryPool<Node<T> > nodes_buffer_;
    Eigen::Vector3f origin_position_ = Eigen::Vector3f::Zero();

    friend class ray_iterator<T>;
    friend class node_iterator<T>;

    // Allocation specific variables
    key_t* keys_at_level_;
    int reserved_;

	std::vector<key_t> all_keys_;

    // Private implementation of cached methods
    value_type get(const int x, const int y, const int z, VoxelBlock<T>* cached) const;
    value_type get(const Eigen::Vector3f& pos, VoxelBlock<T>* cached) const;

    // Parallel allocation of a given tree level for a set of input keys.
    // Pre: levels above target_level must have been already allocated
    bool allocate_level(key_t* keys, int num_tasks, int target_level, int pose);

    void reserveBuffers(const int n);

    // General helpers

    int leavesCountRecursive(Node<T>*);
    int nodeCountRecursive(Node<T>*);
    void getActiveBlockList(Node<T>*, std::vector<VoxelBlock<T>*>& blocklist);
    void getAllocatedBlockList(Node<T>*, std::vector<VoxelBlock<T>*>& blocklist);

    void deleteNode(Node<T>** node);
    void deallocateTree() { deleteNode(&root_); }

	void build_octant_list(const std::vector<Eigen::Vector3f>& world_points, const Eigen::Matrix4f& T_wc, const float zmin, const float zmax, const float band);
};

template <typename T>
Octree<T>::Octree(const Octree<T>& octree)
{
    int size = octree.size();
    float dim = octree.dim();

    init(size, dim);

    leaves_level_ = octree.max_node_level();
    init_size_ = octree.init_size();

    // Copy construct the memory holding the nodes and the leaves
    block_buffer_ = octree.block_buffer_;
    nodes_buffer_ = octree.nodes_buffer_;

    origin_position_ = octree.getOrigin();
}

template <typename T>
Octree<T>& Octree<T>::operator+=(const Octree<T>& octree)
{
    if (size_ == 0 || dim_ == 0) {
        init(octree.size(), octree.dim());
    }

    const int max_blocks = VoxelBlock<T>::sideSq * VoxelBlock<T>::side;
    auto& block_list = octree.block_buffer_;
    size_t list_size = block_list.size();
    for (unsigned int i = 0; i < list_size; ++i) {
        VoxelBlock<T>* block = static_cast<VoxelBlock<T>*>(block_list[i]);
        Eigen::Vector3i coords = block->coordinates();
        VoxelBlock<T>* p = this->fetch(coords(0), coords(1), coords(2));
        if (!p) {
            VoxelBlock<T>* tmp = this->insert(coords(0), coords(1), coords(2), 0);
            std::memcpy(tmp->getBlockRawPtr(), block->getBlockRawPtr(), max_blocks * sizeof(*(tmp->getBlockRawPtr())));
        }
    }

    auto& nodes_list = octree.nodes_buffer_;
    list_size = nodes_list.size();
    for (unsigned int i = 0; i < list_size; ++i) {
        se::Node<T>* node = static_cast<Node<T>*>(nodes_list[i]);
        se::key_t key = node->code_;
        se::key_t code = se::keyops::code(key);
        const int level = se::keyops::level(code);
        Eigen::Vector3i coords = se::keyops::decode(code);
        Node<T>* p = this->fetch_octant(coords(0), coords(1), coords(2), leaves_level_);
        if (!p) {
            Node<T>* tmp = this->insert(coords(0), coords(1), coords(2), level, 0);
            std::memcpy(tmp->value_, node->value_, sizeof(tmp->value_));
        }
    }
    return *this;
}

template <typename T>
inline typename Octree<T>::value_type Octree<T>::get(const Eigen::Vector3f& p, VoxelBlock<T>* cached) const
{
    const Eigen::Vector3i pos = (p.homogeneous() * Eigen::Vector4f::Constant(size_ / dim_)).head<3>().cast<int>();

    if (cached != NULL) {
        Eigen::Vector3i lower = cached->coordinates();
        Eigen::Vector3i upper = lower + Eigen::Vector3i::Constant(blockSide - 1);
        const int contained = ((pos.array() >= lower.array()) * (pos.array() <= upper.array())).all();
        if (contained) {
            return cached->data(pos);
        }
    }

    Node<T>* n = root_;
    if (!n) {
        return empty();
    }

    // Get the block.

    unsigned edge = size_ >> 1;
    for (; edge >= blockSide; edge = edge >> 1) {
        n = n->child((pos(0) & edge) > 0, (pos(1) & edge) > 0, (pos(2) & edge) > 0);
        if (!n) {
            return empty();
        }
    }

    // Get the element in the voxel block
    return static_cast<VoxelBlock<T>*>(n)->data(pos);
}

template <typename T>
inline void Octree<T>::set(const int x, const int y, const int z, const value_type val)
{
    Node<T>* n = root_;
    if (!n) {
        return;
    }

    unsigned edge = size_ >> 1;
    for (; edge >= blockSide; edge = edge >> 1) {
        Node<T>* tmp = n->child((x & edge) > 0, (y & edge) > 0, (z & edge) > 0);
        if (!tmp) {
            return;
        }
        n = tmp;
    }

    static_cast<VoxelBlock<T>*>(n)->data(Eigen::Vector3i(x, y, z), val);
}

template <typename T>
inline typename Octree<T>::value_type Octree<T>::get(const int x, const int y, const int z) const
{
    Node<T>* n = root_;
    if (!n) {
        return init_val();
    }

    unsigned edge = size_ >> 1;
    for (; edge >= blockSide; edge = edge >> 1) {
        const int childid = ((x & edge) > 0) + 2 * ((y & edge) > 0) + 4 * ((z & edge) > 0);
        Node<T>* tmp = n->child(childid);
        if (!tmp) {
            return n->value_[childid];
        }
        n = tmp;
    }

    return static_cast<VoxelBlock<T>*>(n)->data(Eigen::Vector3i(x, y, z));
}

template <typename T>
inline typename Octree<T>::value_type Octree<T>::get_fine(const int x, const int y, const int z) const
{
    Node<T>* n = root_;
    if (!n) {
        return init_val();
    }

    unsigned edge = size_ >> 1;
    for (; edge >= blockSide; edge = edge >> 1) {
        const int childid = ((x & edge) > 0) + 2 * ((y & edge) > 0) + 4 * ((z & edge) > 0);
        Node<T>* tmp = n->child(childid);
        if (!tmp) {
            return init_val();
        }
        n = tmp;
    }

    return static_cast<VoxelBlock<T>*>(n)->data(Eigen::Vector3i(x, y, z));
}

template <typename T>
inline typename Octree<T>::value_type Octree<T>::get(const int x, const int y, const int z, VoxelBlock<T>* cached) const
{
    if (cached != NULL) {
        const Eigen::Vector3i pos = Eigen::Vector3i(x, y, z);
        const Eigen::Vector3i lower = cached->coordinates();
        const Eigen::Vector3i upper = lower + Eigen::Vector3i::Constant(blockSide - 1);
        const int contained = ((pos.array() >= lower.array()) && (pos.array() <= upper.array())).all();
        if (contained) {
            return cached->data(Eigen::Vector3i(x, y, z));
        }
    }

    Node<T>* n = root_;
    if (!n) {
        return init_val();
    }

    unsigned edge = size_ >> 1;
    for (; edge >= blockSide; edge = edge >> 1) {
        n = n->child((x & edge) > 0, (y & edge) > 0, (z & edge) > 0);
        if (!n) {
            return init_val();
        }
    }

    return static_cast<VoxelBlock<T>*>(n)->data(Eigen::Vector3i(x, y, z));
}

template <typename T>
void Octree<T>::deleteNode(Node<T>** node)
{
    if (*node) {
        for (int i = 0; i < 8; i++) {
            if ((*node)->child(i)) {
                deleteNode(&(*node)->child(i));
            }
        }
        if (!(*node)->isLeaf()) {
            delete *node;
            *node = NULL;
        }
    }
}

template <typename T>
Eigen::Vector3f Octree<T>::expand(Eigen::Vector3i directions)
{
    int x_dir = directions(0), y_dir = directions(1), z_dir = directions(2);
    /***
     * if(x_dir == 0 && y_dir == 0 && z_dir ==0) return;
     * root_x = root_y = root_z = 0;
     * if(x_dir == 1 || x_dir == 0){
     *    broaden x from [0:size] to [0:2*size]
     *    root_x = 0
     * } else {
     *    broaden x from [0:size] to [-size, size]
     *    root_x = size
     * }
     * if(y_dir == 1 || y_dir == 0){
     *    broaden y from [0:size] to [0:2*size]
     *    root_y = 0
     * } else {
     *    broaden y from [0:size] to [-size, size]
     *    root_y = size
     * }
     * if(z_dir == 1 || z_dir == 0){
     *    broaden z from [0:size] to [0:2*size]
     *    root_z = 0
     * } else {
     *    broaden z from [0:size] to [-size, size]
     *    root_z = size
     * }
     * **/
    assert(x_dir == 0 || x_dir == 1 || x_dir == -1);
    assert(y_dir == 0 || y_dir == 1 || y_dir == -1);
    assert(z_dir == 0 || z_dir == 1 || z_dir == -1);
    if (x_dir == 0 && y_dir == 0 && z_dir == 0) return Eigen::Vector3f(0, 0, 0);
    int pos_x = (x_dir == -1) ? size_ : 0;
    int pos_y = (y_dir == -1) ? size_ : 0;
    int pos_z = (z_dir == -1) ? size_ : 0;
    size_ = size_ * 2;
    dim_ = dim_ * 2;
    max_level_ = log2(size_);
    leaves_level_ = max_level_ - math::log2_const(blockSide);
    // change block key accordingly
    auto& block_list = getBlockBuffer();
    size_t list_size = block_list.size();
#ifdef USE_OPENMP
#pragma omp parallel for
#endif
    for (unsigned int i = 0; i < list_size; ++i) {
        se::VoxelBlock<T>* block = static_cast<VoxelBlock<T>*>(block_list[i]);
        se::key_t old_key = block->code_;
        se::key_t old_code = se::keyops::code(old_key);
        int old_level = se::keyops::level(old_key);
        Eigen::Vector3i coords = se::keyops::decode(old_code);
        se::key_t code = old_code;
        code = se::keyops::encode(coords(0) + pos_x, coords(1) + pos_y, coords(2) + pos_z, old_level + 1, max_level_);
        block->code_ = code | (old_level + 1);
        block->coordinates(se::keyops::decode(block->code_));
    }
    // change block key accordingly
    auto& nodes_list = getNodesBuffer();
    list_size = nodes_list.size();
#ifdef USE_OPENMP
#pragma omp parallel for
#endif
    for (unsigned int i = 0; i < list_size; ++i) {
        se::Node<T>* node = static_cast<Node<T>*>(nodes_list[i]);
        se::key_t old_key = node->code_;
        se::key_t old_code = se::keyops::code(old_key);
        int old_level = se::keyops::level(old_key);
        Eigen::Vector3i coords = se::keyops::decode(old_code);
        se::key_t code = old_code;
        code = se::keyops::encode(coords(0) + pos_x, coords(1) + pos_y, coords(2) + pos_z, old_level + 1, max_level_);
        node->code_ = code | (old_level + 1);
    }

    // add a new root
    Node<T>* o_root_ = root_;
    root_ = nodes_buffer_.acquire_block();
    root_->side_ = size_;

    unsigned edge = size_ >> 1;
    root_->child((pos_x & edge) > 0, (pos_y & edge) > 0, (pos_z & edge) > 0) = o_root_;
    float voxel_size = dim_ / size_;
    return Eigen::Vector3f(pos_x * voxel_size, pos_y * voxel_size, pos_z * voxel_size);
}

template <typename T>
void Octree<T>::init(int size, float dim)
{
    init_size_ = size_ = size;
    dim_ = dim;
    max_level_ = log2(size);
    leaves_level_ = max_level_ - math::log2_const(blockSide);
    nodes_buffer_.reserve(1);
    root_ = nodes_buffer_.acquire_block();
    root_->side_ = size;

    reserved_ = 1024;
    keys_at_level_ = new key_t[reserved_];
    std::memset(keys_at_level_, 0, reserved_);
}

template <typename T>
void Octree<T>::clear()
{
    if (!root_) return;
    int size = root_->side_;
    block_buffer_.release_all(true);
    nodes_buffer_.release_all(true);
    root_ = nodes_buffer_.acquire_block();
    root_->side_ = size;
    std::memset(keys_at_level_, 0, reserved_);
}

template <typename T>
inline VoxelBlock<T>* Octree<T>::fetch(const int x, const int y, const int z) const
{
    Node<T>* n = root_;
    if (!n) {
        return NULL;
    }

    // Get the block.
    unsigned edge = size_ / 2;
    for (; edge >= blockSide; edge /= 2) {
        n = n->child((x & edge) > 0u, (y & edge) > 0u, (z & edge) > 0u);
        if (!n) {
            return NULL;
        }
    }
    return static_cast<VoxelBlock<T>*>(n);
}

template <typename T>
inline Node<T>* Octree<T>::fetch_octant(const int x, const int y, const int z, const int depth) const
{
    Node<T>* n = root_;
    if (!n) {
        return NULL;
    }

    // Get the block.
    unsigned edge = size_ / 2;
    for (int d = 1; edge >= blockSide && d <= depth; edge /= 2, ++d) {
        n = n->child((x & edge) > 0u, (y & edge) > 0u, (z & edge) > 0u);
        if (!n) {
            return NULL;
        }
    }
    return n;
}

template <typename T>
VoxelBlock<T> * Octree<T>::insert(const int x, const int y, const int z, const int pose) {
  return static_cast<VoxelBlock<T> * >(insert(x, y, z, max_level_, pose));
}

template <typename T>
Node<T>* Octree<T>::insert(const int x, const int y, const int z, const int depth, const int pose)
{
    // Make sure we have enough space on buffers
    if (depth >= leaves_level_) {
        block_buffer_.reserve(1);
        nodes_buffer_.reserve(leaves_level_);
    } else {
        nodes_buffer_.reserve(depth);
    }

    Node<T>* n = root_;
    // Should not happen if octree has been initialised properly
    if (!n) {
        root_ = nodes_buffer_.acquire_block();
        root_->code_ = 0;
        root_->side_ = size_;
        root_->poseId_ = pose;
        n = root_;
    }

    key_t key = keyops::encode(x, y, z, depth, max_level_);
    const unsigned int shift = MAX_BITS - max_level_ - 1;

    unsigned edge = size_ / 2;
    for (int d = 1; edge >= blockSide && d <= depth; edge /= 2, ++d) {
        const int childid = ((x & edge) > 0) + 2 * ((y & edge) > 0) + 4 * ((z & edge) > 0);

        Node<T>* tmp = n->child(childid);
        if (!tmp) {
            const key_t prefix = keyops::code(key) & MASK[d + shift];
            if (edge == blockSide) {
                tmp = block_buffer_.acquire_block();
                static_cast<VoxelBlock<T>*>(tmp)->coordinates(Eigen::Vector3i(unpack_morton(prefix)));
                static_cast<VoxelBlock<T>*>(tmp)->active(true);
                static_cast<VoxelBlock<T>*>(tmp)->code_ = prefix | d;
                static_cast<VoxelBlock<T>*>(tmp)->poseId_ = pose;
                n->children_mask_ = n->children_mask_ | (1 << childid);
            } else {
                tmp = nodes_buffer_.acquire_block();
                tmp->code_ = prefix | d;
                tmp->side_ = edge;
                tmp->poseId_ = pose;
                n->children_mask_ = n->children_mask_ | (1 << childid);
            }
            n->child(childid) = tmp;
        }
        n = tmp;
    }
    return n;
}

template <typename T>
int Octree<T>::leavesCount()
{
    return leavesCountRecursive(root_);
}

template <typename T>
int Octree<T>::leavesCountRecursive(Node<T>* n)
{
    if (!n) return 0;

    if (n->isLeaf()) {
        return 1;
    }

    int sum = 0;

    for (int i = 0; i < 8; i++) {
        sum += leavesCountRecursive(n->child(i));
    }

    return sum;
}

template <typename T>
int Octree<T>::nodeCount()
{
    return nodeCountRecursive(root_);
}

template <typename T>
int Octree<T>::nodeCountRecursive(Node<T>* node)
{
    if (!node) {
        return 0;
    }

    int n = 1;
    for (int i = 0; i < 8; ++i) {
        n += (n ? nodeCountRecursive((node)->child(i)) : 0);
    }
    return n;
}

template <typename T>
void Octree<T>::reserveBuffers(const int n)
{
    if (n > reserved_) {
        delete[] keys_at_level_;
        keys_at_level_ = new key_t[n];
        reserved_ = n;
    }
    block_buffer_.reserve(n);
}

template <typename T>
void Octree<T>::allocate_points(const std::vector<Eigen::Vector3f>& world_points,
	const Eigen::Matrix4f& pose, const float zmin, const float zmax,
	const float band, const int pose_id)
{
	build_octant_list(world_points, pose, zmin, zmax, band);
	allocate(all_keys_.data(), all_keys_.size(), pose_id);
}

template <typename T>
bool Octree<T>::allocate(key_t* keys, int num_elem, int pose)
{
    if (!num_elem) return false;

#if defined(_OPENMP) && !defined(__clang__)
    __gnu_parallel::sort(keys, keys + num_elem);
#else
    std::sort(keys, keys + num_elem);
#endif

    num_elem = algorithms::filter_ancestors(keys, num_elem, max_level_);
    reserveBuffers(num_elem);

    int last_elem = 0;
    bool success = false;

    const unsigned int shift = MAX_BITS - max_level_ - 1;
    for (int level = 1; level <= leaves_level_; level++) {
        const key_t mask = MASK[level + shift] | SCALE_MASK;
        compute_prefix(keys, keys_at_level_, num_elem, mask);
        last_elem = algorithms::unique_multiscale(keys_at_level_, num_elem, SCALE_MASK, level);
        success = allocate_level(keys_at_level_, last_elem, level, pose);
    }
    return success;
}

template <typename T>
bool Octree<T>::allocate_level(key_t* keys, int num_tasks, int target_level, int pose)
{
    nodes_buffer_.reserve(num_tasks);
#ifdef USE_OPENMP
#pragma omp parallel for
#endif
    for (int i = 0; i < num_tasks; i++) {
        Node<T>** n = &root_;
        key_t myKey = keyops::code(keys[i]);
        int edge = size_ / 2;

        for (int level = 1; level <= target_level; ++level) {
            int index = keyops::child_id(myKey, level, max_level_);
            Node<T>* parent = *n;
            n = &(*n)->child(index);

            if (!(*n)) {
                if (level == leaves_level_) {
                    *n = block_buffer_.acquire_block();
                    (*n)->side_ = edge;
                    static_cast<VoxelBlock<T>*>(*n)->coordinates(Eigen::Vector3i(unpack_morton(myKey)));
                    static_cast<VoxelBlock<T>*>(*n)->active(true);
                    static_cast<VoxelBlock<T>*>(*n)->code_ = myKey | level;
                    static_cast<VoxelBlock<T>*>(*n)->poseId_ = pose;
                    parent->children_mask_ = parent->children_mask_ | (1 << index);
                } else {
                    *n = nodes_buffer_.acquire_block();
                    (*n)->code_ = myKey | level;
                    (*n)->side_ = edge;
                    (*n)->poseId_ = pose;
                    parent->children_mask_ = parent->children_mask_ | (1 << index);
                }
            }
            edge /= 2;
        }
    }
    return true;
}

template <typename T>
void Octree<T>::getBlockList(std::vector<VoxelBlock<T>*>& blocklist, bool active)
{
    Node<T>* n = root_;
    if (!n) return;
    if (active)
        getActiveBlockList(n, blocklist);
    else
        getAllocatedBlockList(n, blocklist);
}

template <typename T>
void Octree<T>::getActiveBlockList(Node<T>* n, std::vector<VoxelBlock<T>*>& blocklist)
{
    using tNode = Node<T>;
    if (!n) return;
    std::queue<tNode*> q;
    q.push(n);
    while (!q.empty()) {
        tNode* node = q.front();
        q.pop();

        if (node->isLeaf()) {
            VoxelBlock<T>* block = static_cast<VoxelBlock<T>*>(node);
            if (block->active()) blocklist.push_back(block);
            continue;
        }

        for (int i = 0; i < 8; ++i) {
            if (node->child(i)) q.push(node->child(i));
        }
    }
}

template <typename T>
void Octree<T>::getAllocatedBlockList(Node<T>*, std::vector<VoxelBlock<T>*>& blocklist)
{
    for (unsigned int i = 0; i < block_buffer_.size(); ++i) {
        blocklist.push_back(block_buffer_[i]);
    }
}

template <typename T>
void Octree<T>::build_octant_list(const std::vector<Eigen::Vector3f>& world_points,
	const Eigen::Matrix4f& T_wc, const float zmin, const float zmax,
	const float band)
{
    const float voxel_size = dim_ / size_;
    const float inverse_voxel_size = 1.f / voxel_size;

	if(!all_keys_.empty()) all_keys_.clear();

    Eigen::Vector3f camera = T_wc.topRightCorner<3, 1>();

    for (size_t vid = 0; vid < world_points.size(); vid++) {
        int tree_depth = max_level_;
        float step_size = voxel_size;

        Eigen::Vector3f worldVertex = world_points[vid];
        Eigen::Vector3f direction = (camera - worldVertex).normalized();
        Eigen::Vector3f origin = worldVertex - (band * 0.5f) * direction;
        Eigen::Vector3f step = direction * step_size;
        Eigen::Vector3f voxelPos = origin;
        const float dist = (camera - origin).norm();

		auto is_voxel_valid = [=](const Eigen::Vector3f& v)
		{
			return ((v.x() >= 0) && (v.x() < size_) &&
				(v.y() >= 0) && (v.y() < size_) &&
				(v.z() >= 0) && (v.z() < size_));
		};

		float travelled = 0.f;

        for (; travelled < dist; travelled += step_size) {
			float height = voxelPos.z();
            if (height >= zmin && height <= zmax) {
                Eigen::Vector3f voxelScaled = (voxelPos * inverse_voxel_size).array().floor();
				if (is_voxel_valid(voxelScaled)) {
                    const Eigen::Vector3i voxel = voxelScaled.cast<int>();
                    auto n = fetch_octant(voxel.x(), voxel.y(), voxel.z(), tree_depth);
                    if (!n) {
                        auto k = hash(voxel.x(), voxel.y(), voxel.z(), std::min(tree_depth, leaves_level_));
						all_keys_.emplace_back(k);
                    } else if (tree_depth >= leaves_level_) {
                        static_cast<VoxelBlock<T>*>(n)->active(true);
                    }
                }
			}

			// Determine step size depending on the distance that we traversed on the ray
			auto compute_step_size = [=]()
			{
				float new_step;
				float half = band * 0.5f;
				if(travelled < band)
					new_step = voxel_size;
				else if(travelled < band + half)
					new_step = 10.f * voxel_size;
				else
					new_step = 30.f * voxel_size;
            	return new_step;
			};

            step_size = compute_step_size();

			// Compute depth in the tree depending on the current step - distance in the ray
			auto step_to_tree_depth = [=]()
			{
				return static_cast<int>(floorf(std::log2f(voxel_size/step_size)) + max_level_);
			};
			tree_depth = step_to_tree_depth();
            step = direction * step_size;
            voxelPos += step;
        }
    }
}

template <typename T>
void Octree<T>::setOriginPosition(const Eigen::Vector3f& pos)
{
    origin_position_ = pos;
}

template <typename T>
const Eigen::Vector3f Octree<T>::getOrigin() const
{
    return origin_position_;
}
}  // namespace se
#endif  // OCTREE_H
