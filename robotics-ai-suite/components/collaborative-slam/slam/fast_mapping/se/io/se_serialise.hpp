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

#ifndef SE_SERIALISE_HPP
#define SE_SERIALISE_HPP
#include <fstream>
#include "../octree_defines.h"
#include "Eigen/Dense"

namespace se {

template <typename T>
class Node;

template <typename T>
class VoxelBlock;

namespace internal {
/*
 * \brief Write node's data to output file out. We do not serialise child
 * pointers and mask as those will be reconstructed when deserialising.
 * \param out Binary output file
 * \param node Node to be serialised
 */
template <typename T>
void serialise(std::ofstream& out, Node<T>& node) {
    out.write(reinterpret_cast<char *>(&node.code_), sizeof(key_t));
    out.write(reinterpret_cast<char *>(&node.side_), sizeof(int));
    out.write(reinterpret_cast<char *>(&node.value_), sizeof(node.value_));
    out.write(reinterpret_cast<char *>(&node.pose_id_), sizeof(node.pose_id_));
}

/*
 * \brief Read node's data from input binary file. We do not read child
 * pointers and mask as those will be reconstructed when deserialising.
 * \param node Node to be deserialised
 * \param in Binary input file
 */
template <typename T>
void deserialise(Node<T>& node, std::ifstream& in) {
    in.read(reinterpret_cast<char *>(&node.code_), sizeof(key_t));
    in.read(reinterpret_cast<char *>(&node.side_), sizeof(int));
    in.read(reinterpret_cast<char *>(&node.value_), sizeof(node.value_));
    in.read(reinterpret_cast<char *>(&node.pose_id_), sizeof(node.pose_id_));
}

/*
 * \brief Write VoxelBlock's data to output file out. 
 * \param out Binary output file
 * \param block Voxel block to be serialised
 */
template <typename T>
void serialise(std::ofstream& out, VoxelBlock<T>& block) {
    out.write(reinterpret_cast<char *>(&block.code_), sizeof(key_t));
    out.write(reinterpret_cast<char *>(block.coordinates_.data()), sizeof(block.coordinates_));
    out.write(reinterpret_cast<char *>(&block.voxel_block_), sizeof(block.voxel_block_));
    out.write(reinterpret_cast<char *>(&block.pose_id_), sizeof(block.pose_id_));
}

/*
 * \brief Read node's data from input binary file. We do not read child
 * pointers and mask as those will be reconstructed when deserialising.
 * \param block Voxel block to be serialised
 * \param in Binary input file
 */
template <typename T>
void deserialise(VoxelBlock<T>& block, std::ifstream& in) {
    in.read(reinterpret_cast<char *>(&block.code_), sizeof(key_t));
    in.read(reinterpret_cast<char *>(block.coordinates_.data()), sizeof(block.coordinates_));
    in.read(reinterpret_cast<char *>(&block.voxel_block_), sizeof(block.voxel_block_));
    in.read(reinterpret_cast<char *>(&block.pose_id_), sizeof(block.pose_id_));
}

} // namespace internal
} // namespace se
#endif
