# ITS Path Planner Plugin Customization
<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

The ROS 2 navigation bring-up application is started using 
the TurtleBot 3 Gazebo simulation
and it receives as input parameter `nav2_params_jazzy.yaml`.

To use the ITS path planner plugin, the following parameters are added in
`nav2_params_jazzy.yaml`:

```yaml
planner_server:
  ros__parameters:
    expected_planner_frequency: 20.0
    use_sim_time: True
    planner_plugins: ["GridBased"]
    costmap_update_timeout: 1.0
    GridBased:
      plugin: "its_planner/ITSPlanner"
      interpolation_resolution: 0.05
      catmull_spline: False
      smoothing_window: 15
      buffer_size: 10
      build_road_map_once: True
      enable_k: False
      min_samples: 250
      roadmap: "PROBABLISTIC"
      w: 32
      h: 32
      n: 2
```


<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

The ROS 2 navigation bring-up application is started using 
the TurtleBot 3 Gazebo simulation
and it receives as input parameter `nav2_params_humble.yaml`.

To use the ITS path planner plugin, the following parameters are added in
`nav2_params_humble.yaml`:

```yaml
planner_server:
  ros__parameters:
    expected_planner_frequency: 0.01
    use_sim_time: True
    planner_plugins: ["GridBased"]
    GridBased:
      plugin: "its_planner/ITSPlanner"
      interpolation_resolution: 0.05
      catmull_spline: False
      smoothing_window: 15
      buffer_size: 10
      build_road_map_once: True
      enable_k: False
      min_samples: 250
      roadmap: "PROBABLISTIC"
      w: 32
      h: 32
      n: 2
```


## ITS Path Planner Plugin Parameters

```bash
catmull_spline:
```

If true, the generated path from the ITS is interpolated with the catmull
spline method; otherwise, a smoothing filter is used to smooth the path.

```bash
smoothing_window:
```

The window size for the smoothing filter (The unit is the grid size.)

```bash
buffer_size:
```

During roadmap generation, the samples are generated away from obstacles. The
buffer size dictates how far away from obstacles the roadmap samples should be.

```bash
build_road_map_once:
```

If true, the roadmap is loaded from the saved file; otherwise, a new roadmap
is generated.

```bash
min_samples:
```

The minimum number of samples required to generate the roadmap

```bash
roadmap:
```

Either PROBABILISTIC or DETERMINISTIC

```bash
w:
```

The width of the window for intelligent sampling

```bash
h:
```

The height of the window for intelligent sampling

```bash
n:
```

The minimum number of samples that is required in an area defined by `w` and
`h`

## ITS Path Planner Plugin Parameters modification

### Default ITS Planner 
You can modify plugin parameters by editing the `planner_server` section 
in the configuration file below for the `default ITS planner`:


<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
/opt/ros/jazzy/share/its_planner/nav2_params_jazzy.yaml
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
/opt/ros/humble/share/its_planner/nav2_params_humble.yaml
```

<!--hide_directive:::
::::hide_directive-->

### Ackermann ITS Planner
You can modify plugin parameters by editing the `planner_server` section 
in the configuration file below for the `Ackermann ITS planner`:

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
/opt/ros/jazzy/share/its_planner/nav2_params_dubins_jazzy.yaml
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
/opt/ros/humble/share/its_planner/nav2_params_dubins_humble.yaml
```

<!--hide_directive:::
::::hide_directive-->
