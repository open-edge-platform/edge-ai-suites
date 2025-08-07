uint64 mn_id # unique KF id
uint8 mn_client_id # client id
uint32 mn_localize_map_id
float64 md_timestamp
#Number of KeyPoints
uint32 mn_num_keypoints
#KeyPoints, depths, stereo coordinate and descriptors (all associated by an index)
CvKeypoint[] mv_keypoints
Descriptor[] mv_descriptors
#Pose in the world
float32[16] mv_pose
#Scale
int8 mn_scale_levels
float32 mf_scale_factor
float32 mf_log_scale_factor

#for multi-slam system
uint64 mn_src_frame_id
float32[] mv_stereo_x_right
float32 mf_depth_thr
uint64 mn_parent_id
uint64[] mv_children_ids

# for imu reset
bool mb_bad_imu_to_reset
