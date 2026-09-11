# Install UAV Vision Analytics Application

The UAV Vision Analytics application supports two deployment modes:

- **[Standalone Mode (pymavlink)](./get-started/get-started-standalone.md)** — Use this if you want to try the application on its own, with no other services required. It runs a self-contained PX4 SITL flight simulation and reads telemetry directly over pymavlink, using a single sample/looped video (or a RealSense camera) as the source. Best for first-time evaluation, demos, and quick testing.
- **[UAV Mission Compute SDK Mode](./get-started/get-started-uavsdk.md)** — Use this if you already have the UAV Mission Compute SDK running (with a real drone or its own simulation) and want to attach multi-camera (nadir/forward/rear) AI inference and mission-aware pipeline control to it. Requires the SDK stack to be started first.

<!--hide_directive
:::{toctree}
:hidden:

Standalone Mode <./get-started/get-started-standalone.md>
UAV Mission Compute SDK Mode <./get-started/get-started-uavsdk.md>

:::
hide_directive-->
