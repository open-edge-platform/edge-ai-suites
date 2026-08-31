# Compilation

The unit tests can be compiled as follows:

```bash
cd frameworks.industrial.robotics.rvc.control/rvc_grasp/rvc_grasp_plugins/oriented_grasp
colcon build --packages-select oriented_grasp --symlink-install --cmake-args -DBUILD_TESTING=ON
```

Please note that this command builds all the other tests present in the project as well.

## Execution

Before to execute the tests, it is necessary to source the environment:

```bash
source install/setup.bash
```

The provided unit tests can be executed as follows:

```bash
colcon test --packages-select oriented_grasp --ctest-args -R 'oriented_grasp_*'
```

More information is reported by passing an additional argument:

```bash
colcon test --packages-select oriented_grasp --event-handlers console_direct+ --ctest-args -R 'oriented_grasp_*'
```
