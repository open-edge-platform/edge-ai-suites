# Release Notes: Smart Classroom

## Version 2026.0

**April 1, 2026**

The Smart Classroom application now offers a series after-class summary enhancements in the form of next‑generation real-time audio and visual analytics, giving teachers and schools a better understanding of classroom dynamics through AI‑driven summaries and engagement metrics.

The Education AI Suite now also includes built-in telemetry hooks and benchmarking.

**New**

- **Speaker Diarization** (via the Audio Pipeline):
  - identifies teacher and student speakers using NPU-accelerated diarization
  - generates an interactive audio timeline for replay and analysis
  - enables time-coded navigation within class video recordings

- **Class Engagement Metrics – Audio**:
  - measure teacher and student speech duration
  - track questions asked and answered
  - track student-teacher interaction frequency

- **Class Engagement Metrics – Video**:
  - track student hand raises
  - track posture changes (stand up/sit down)
  - track teacher movement

- **Built‑in telemetry** to measure classroom workloads across Intel platforms (CPU core utilization, iGPU load, NPU load, memory usage, workload-specific performance counters)

- **Benchmarking scripts** to reproduce Intel internal performance measurements, and validate XPU performance

**Improved**

- **Knowledge Graph UI** readability and formatting, and increased clarity when visualizing topic relationships

## Documentation and Source Code

- [GitHub](https://github.com/open-edge-platform/edge-ai-suites/tree/main/education-ai-suite)

## Previous releases

- [Release notes 2025](./release-notes/release-notes-2025.md)

<!--hide_directive
:::{toctree}
:hidden:

Release Notes 2025 <./release-notes/release-notes-2025.md>

:::
hide_directive-->