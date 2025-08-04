### How to enable map generation using the integrated Fast mapping module


**General description of Fast Mapping module**
Using the RGB-D data from the camera and the current pose resulting from the tracking module, the Fast Mapping module generates and maintains both a volumetric map (3D) and a occupancy grid (2D) that can be used for robot navigation.


**Expected Behaviour** When enabled through a ROS configuration parameter, Fast Mapping will create two output topics for both of the map as follows: ```/fused map``` - 3D map and ```/map``` - 2D Occupancy Grid.


### How To enable and configure Fast mapping parameters

1. Main parameters to be set:


| Parameter                     | Description                                                                                 | Type   | Default Value | Unit   |
|-------------------------------|---------------------------------------------------------------------------------------------|--------|---------------|--------|
| enable_fast_mapping           | Flag to enable/disable Fast Mapping                                                         | bool   | false         | -      |
| depth_max_range               | Maximum range of the camera input                                                           | double | 3.3           | meters |
| voxel_size                    | Map resolution in voxels                                                                    | double | 0.04          | meters |
| zmin/max                      | Min and max height of the Field of View                                                     | double | 0.30 0.6      | meters |
| map_size                      | Size of the octree                                                                          | int    | 256           | voxels |
| depth_scalling_factor         | Scalling factor of the depth images                                                         | int    | 2             | -      |
| correction_threshold          | Lower threshold for accepting a loop closure correction                                     | int    | 4             | voxels |


### Loop Closure map correction

Fast Mapping can perform map correction of both 3D and 2D as a result of a loop closure detected by the server.
However, if the correction is smaller then ```correction_threshold``` the loop closure will be ignored since
the correction will be too small to influence the quality of the generated map.

The fast mapping module will generated the following console output when loop correction or map merge happens in server.

1. If map gets updated : ```Begin tracker octree correction after loop correction or map merge```
2. If loop closure will be ignored: ```Correction is too small to trigger tracker octree update```


### Map Merging

Collaborative SLAM can perform map merging of the 3D and 2D from multiple trackers. As a result of map
merging each tracker involved in the map merging will receive the updated map and will be visible in one
of the above mentioned topics.

The fast mapping module will generate the following console output when map merging will happen: ```Received merged octree from server```
