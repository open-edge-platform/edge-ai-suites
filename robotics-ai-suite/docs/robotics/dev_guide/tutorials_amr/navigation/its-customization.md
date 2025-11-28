# ITS Path Planner Plugin Customization

The ROS 2 navigation bring-up application is started using the TurtleBot 3 Gazebo
simulation, and it receives as input parameter its_nav2_params.yaml.

To use the ITS path planner plugin, the following parameters are added in
its_nav2_params.yaml:

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
>       min_samples: 250
>       roadmap: "PROBABLISTIC"
>       w: 32
>       h: 32
>       n: 2
> ```

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

You can modify these values by editing the file below for the default
ITS planner, at lines 274-291:

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1hide_directive-->

```bash
/opt/ros/jazzy/share/its_planner/nav2_params.yaml
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: tab2hide_directive-->

```bash
/opt/ros/humble/share/its_planner/nav2_params.yaml
```

<!--hide_directive:::
::::hide_directive-->

You can modify these values by editing the file below for the Ackermann ITS planner, at lines 274-296:

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1hide_directive-->

```bash
/opt/ros/jazzy/share/its_planner/nav2_params_dubins.yaml
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: tab2hide_directive-->

```bash
/opt/ros/humble/share/its_planner/nav2_params_dubins.yaml
```

<!--hide_directive:::
::::hide_directive-->
