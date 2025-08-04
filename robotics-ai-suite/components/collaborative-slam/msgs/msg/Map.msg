std_msgs/Header header
uint8 mn_client_id
uint32 msg_id
float64 msg_timestamp
float64 session_start_time

bool connecting_request
bool send_camera_info  #1: send camera info and inform existense   0:send local map
bool only_add_landmarks
bool stop_sending_msg
bool stopped_sending_msg

Keyframe[] keyframes
Landmark[] landmarks
KeyframeUpdate[] keyframe_updates
uint64[] erase_keyframes_id
uint64[] erase_landmarks_id

# Camera info message
CameraInfo[<=1] camera_info

# Global Optimization Counter
uint32 merge_times

# Loop Closure
bool loop_closure

# Relocalization
bool need_relocalization
bool is_relocalization_result

# Localization
bool is_request_for_server_landmarks
uint64 frame_id  # which frame trigger the request for server landmarks

# Fast Mapping Octree request
bool is_request_octree # Request from the server to tracker to send its octree
bool is_merged_octree # Merged octree from server to tracker
bool is_tracker_octree # Octree from tracker to server

# Loaded Octree map (remapping and localization)
bool is_octree_map_loaded

# Related parameters of pre-constructed octree map from tracker to server in localization or remapping modes
OctreeParam[<=1] octree_param

# Octree
Octree[<=1] octree
