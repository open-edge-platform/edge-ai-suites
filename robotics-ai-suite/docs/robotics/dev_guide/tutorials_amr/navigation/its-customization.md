# ITS Path Planner Plugin Customization


## Default ITS planner parameters
<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

The ROS 2 navigation bring-up application is started using the TurtleBot 3 Gazebo simulation and it receives as input parameter `nav2_params_jazzy.yaml`

```bash
/opt/ros/jazzy/share/its_planner/nav2_params_jazzy.yaml
```
You can modify plugin parameters by editing the `planner_server` section
in  `nav2_params_jazzy.yaml`


> ```yaml
> planner_server:
>   ros__parameters:
>     expected_planner_frequency: 20.0
>     use_sim_time: True
>     planner_plugins: ["GridBased"]
>     costmap_update_timeout: 1.0
>     GridBased:
>       plugin: "its_planner/ITSPlanner"
>       interpolation_resolution: 0.05
>       catmull_spline: False
>       smoothing_window: 15
>       buffer_size: 10
>       build_road_map_once: True
>       enable_k: False
>       min_samples: 250
>       roadmap: "PROBABLISTIC"
>       w: 32
>       h: 32
>       n: 2
> ```

<!--hide_directive:::
:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

The ROS 2 navigation bring-up application is started using the TurtleBot 3 Gazebo simulation and it receives as input parameter `nav2_params_humble.yaml`.


```bash
/opt/ros/humble/share/its_planner/nav2_params_humble.yaml
```

You can modify plugin parameters by editing the `planner_server` section
in  `nav2_params_humble.yaml`

> ```yaml
> planner_server:
>   ros__parameters:
>     expected_planner_frequency: 0.01
>     use_sim_time: True
>     planner_plugins: ["GridBased"]
>     GridBased:
>       plugin: "its_planner/ITSPlanner"
>       interpolation_resolution: 0.05
>       catmull_spline: False
>       smoothing_window: 15
>       buffer_size: 10
>       build_road_map_once: True
>       enable_k: False
>       min_samples: 250
>       roadmap: "PROBABLISTIC"
>       w: 32
>       h: 32
>       n: 2
> ```

<!--hide_directive:::
::::hide_directive-->


**Parameter Descriptions**

- `catmull_spline`: if true, the generated path from the ITS will be interpolated with catmull spline method; otherwise smoothing filter will be used to smooth the path
- `smoothing_window`: window size for the smoothing filter; unit is grid size
- `buffer_size`: during the roadmap generation, the samples are generated away from obstacles. The buffer size dictates how far the roadmap samples should be away from obstacles
- `build_road_map_once`: If true, the roadmap will be loaded from the saved file, otherwise a new roadmap will be generated
- `min_samples`: minimum number of samples required to generate the roadmap
- `roadmap`: can be either `PROBABLISTIC` or `DETERMINISTIC`
- `w`: the width of the window for intelligent sampling
- `h`: the height of the window for intelligent sampling
- `n`: the minimum number of samples that is required in an area defined by `w` and `h`


## Ackermann ITS Planner

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

The ROS 2 navigation bring-up application is started using the TurtleBot 3 Gazebo simulation and it receives as input parameter `nav2_params_dubins_jazzy.yaml`

```bash
/opt/ros/jazzy/share/its_planner/nav2_params_dubins_jazzy.yaml
```
You can modify plugin parameters by editing the `planner_server` section
in  `nav2_params_dubins_jazzy.yaml`


> ```yaml
> planner_server:
>   ros__parameters:
>     use_sim_time: True
>     expected_planner_frequency: 20.0
>     planner_plugins: ["GridBased"]
>     costmap_update_timeout: 1.0
>     GridBased:
>       plugin: "its_planner/ITSPlanner"
>       interpolation_resolution: 0.05
>       catmull_spline: False
>       smoothing_window: 15
>       buffer_size: 1
>       build_road_map_once: True
>       enable_k: False
>       min_samples: 250
>       roadmap: "PROBABLISTIC"
>       w: 20
>       h: 20
>       n: 2
>       dubins_path: True
>       turn_radius: 0.22
>       robot_radius: 0.25
>       yaw_tolerance: 0.125
>       use_final_heading: True
> ```

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

The ROS 2 navigation bring-up application is started using
the TurtleBot 3 Gazebo simulation
and it receives as input parameter `nav2_params_dubins_humble.yaml`.


```bash
/opt/ros/humble/share/its_planner/nav2_params_dubins_humble.yaml
```

You can modify plugin parameters by editing the `planner_server` section
in  `nav2_params_dubins_humble.yaml`

> ```yaml
> planner_server:
>   ros__parameters:
>     expected_planner_frequency: 0.01
>     use_sim_time: True
>     planner_plugins: ["GridBased"]
>     GridBased:
>       plugin: "its_planner/ITSPlanner"
>       interpolation_resolution: 0.05
>       catmull_spline: False
>       smoothing_window: 15
>       buffer_size: 1
>       build_road_map_once: True
>       enable_k: False
>       min_samples: 250
>       roadmap: "PROBABLISTIC"
>       w: 40
>       h: 40
>       n: 2
>       dubins_path: True
>       turn_radius: .22
>       robot_radius: .25
>       yaw_tolerance: .125
>       use_final_heading: True
> ```

**Dubins-Specific Parameters - Ackermann ITS planner:**

- `dubins_path`: If true, the ITS algorithm will utilize Dubins Paths to form a global path that can be followed by an Ackermann steering vehicle.
- `turn_radius`: The minimum turning radius of the robot, in world scale.
- `robot_radius`: The radius of the robot, in world scale.
- `yaw_tolerance`: The amount (+/-) by which the heading angles of the end positions of the intermediate Dubins curves may vary, in radians. Does not apply to the final Goal heading.
- `use_final_heading`: Whether to use the goal heading specified by the `geometry_msgs::msg::PoseStamped` message or not.
