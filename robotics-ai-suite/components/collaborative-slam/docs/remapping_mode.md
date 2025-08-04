### What is remapping mode
Remapping mode is one of the operating modes in Collaborative SLAM and targets to update the pre-constructed
keyframe/landmark map and octree map in mapping mode. A manual 2D-region input from user is needed to help
Collaborative SLAM to know which region of pre-constructed maps is pending to be updated. This remapping region
is a quadrilateral and can be either convex or concave. The detailed shape of this remapping region is determined
by the 4 vertexes input by user. Collaborative SLAM will construct local maps on the tracker side and merge it into
the loaded global maps on server side, both for keyframe/landmark map and octree map.

### How to select the remapping region
Currently, we only support updating the maps constructed by Collaborative SLAM in mapping mode. Once you have a
pre-constructed keyframe/landmark map together with a octree map, you can load them in localization mode and visualize
them through the server rviz. It will help you to determine the remapping region by publishing points in the rviz window.
For saving keyframe/landmark map in mapping mode, you can refer to [geekplus_doc.md](geekplus_doc.md). For saving octree map in mapping mode, you
can use `octree_store_path` parameter when launching tracker node. The usage of such parameter is the same as it in
remapping mode in the below section.

The recommended commands to visualize the pre-constructed maps are:
```
# Localization (tracker)
ros2 launch univloc_tracker tracker.launch.py slam_mode:=localization queue_size:=0 gui:=false rviz:=false octree_load_path:=/path_to_saved_octree_map/xx.bin

# Localization (server)
ros2 launch univloc_server server.launch.py server_mode:=localization load_map_path:=/path_to_saved_keyframe_landmark_map/xx.msg
```

Once the tracker node successfully starts up, it will send the loaded octree map to the server node. Then, you can see it
together with the keyframe/landmark map in the server rviz. To determine the vertexes of your remapping region, you can
first click on the **Publish Point** button in the top toolbar, then move your cursor to the point which you want to
select as the remapping region vertex, and finally click your mouse to publish it. To get the detailed coordinate value
of such point, you can use below command:
```
# Subscribe to the published point
ros2 topic echo /clicked_point geometry_msgs/msg/PointStamped
```

### How to run system in remapping mode
The `server_remapping_region` input parameter is used to describe the 4 vertexes of your remapping region. The 4 vertexes must be
in clockwise or anti-clockwise order and in the format of [P1.x, P1.y, ... , P4.x, P4.y]. Besides, the `enable_fast_mapping`
parameter must be set to `true` to enable the fast mapping module. And all the fast mapping related parameters must be set
to the same values as them in the mapping mode.

The recommended commands are:
```
# Remapping (tracker)
ros2 launch univloc_tracker tracker.launch.py slam_mode:=remapping queue_size:=0 gui:=false rviz:=false octree_load_path:=/path_to_saved_octree_map/xx.bin enable_fast_mapping:=true octree_store_path:=/path_for_saving_updated_octree_map/xxx.bin

# Remapping (server)
# Replace the server_remapping_region vertexes by your own
ros2 launch univloc_server server.launch.py server_mode:=remapping load_map_path:=/path_to_saved_keyframe_landmark_map/xx.msg server_remapping_region:="[P1.x, P1.y, ... , P4.x, P4.y]" save_map_path:=/path_for_saving_updated_keyframe_landmark_map/xxx.msg

```

### Some notices
1. The global octree map and keyframe/landmark map within the remapping region, will be updated based on the local map
constructed by the tracker node in remapping mode. But at the same time, the maps outside the remapping region will also be
impacted in current implementation. For the octree map, this kind of impact is slight due to the fast mapping module on the
tracker node will only construct the local octree map, when the current frame is within the remapping region and the local
map has been merged with the global map. To enable it, you need to add `remapping_region` parameter also for the
tracker node and set it to the same value as the `server_remapping_region` parameter in the server node. But for the keyframe/landmark map, all the keyframes and
landmarks constructed by the tracker node will be saved into the final updated global map. The reason behind this kind of
design is to ensure the continuity and quality of the keyframe/landmark map.

2. The reason why the octree map is stored and loaded from the tracker side is because only the tracker node has the latest
octree map in both mapping and remapping mode. But in the future, we may design to let the tracker node send the octree map
to the server node when it is shutting down. Then the octree map can be saved and loaded from the server side just like the
keyframe/landmark map does.

