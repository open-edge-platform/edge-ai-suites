<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Architecture Overview

## System Architecture

```mermaid
flowchart TD
    subgraph ROS["ROS2 System (Local or Remote)"]
        NA[Node A]
        NB[Node B]
        NC[Node C ...]
    end

    subgraph Stack["Monitoring Stack"]
        ORCH["monitor_stack.py\n(Orchestrator)"]
        GRAPH["ros2_graph_monitor.py"]
        RES["monitor_resources.py"]
        CSV[(graph_timing.csv)]
        LOG[(resource_usage.log)]
        VIZ["Auto-Visualization"]

        ORCH --> GRAPH
        ORCH --> RES
        GRAPH --> CSV
        RES --> LOG
        CSV --> VIZ
        LOG --> VIZ
    end

    OUT[("monitoring_sessions/\ntimestamp/")]

    NA -- topics --> GRAPH
    NB -- topics --> GRAPH
    NC -- pids --> RES
    VIZ --> OUT
```

---

## Component Interaction

```mermaid
flowchart TD
    User([User])

    subgraph IFace["Interface Layer"]
        MS[monitor_stack.py]
        MK[Makefile]
    end

    subgraph Core["Core Monitoring Layer"]
        GM[ros2_graph_monitor.py]
        RM[monitor_resources.py]
    end

    subgraph VLayer["Visualization Layer"]
        VT[visualize_timing.py]
        VR[visualize_resources.py]
    end

    OUT[("monitoring_sessions/\ntimestamp/")]

    User --> MS
    User --> MK
    MK --> MS
    MS --> GM
    MS --> RM
    GM --> VT
    RM --> VR
    VT --> OUT
    VR --> OUT
```

---

## Data Flow

```mermaid
flowchart LR
    CMD["uv run python src/monitor_stack.py\n--node /target"]

    subgraph Spawn["Spawn"]
        GM[ros2_graph_monitor.py]
        RM[monitor_resources.py]
    end

    subgraph Collect["Collect"]
        CSV["graph_timing.csv\n• timestamps\n• delays\n• frequencies"]
        LOG["resource_usage.log\n• CPU per thread\n• memory\n• I/O"]
    end

    subgraph Viz["Visualize"]
        VT[visualize_timing.py]
        VR[visualize_resources.py]
        PLOTS["visualizations/*.png"]
    end

    OUT[("session folder")]

    CMD --> GM
    CMD --> RM
    GM --> CSV
    RM --> LOG
    CSV --> VT
    LOG --> VR
    VT --> PLOTS
    VR --> PLOTS
    PLOTS --> OUT
    CSV --> OUT
    LOG --> OUT
```

---

## Session Lifecycle

```mermaid
flowchart LR
    S1["SETUP\nCreate session dir\nInit log files"]
    S2["MONITORING\nLaunch monitors\nCollect data"]
    S3["SHUTDOWN\nCtrl+C received\nGraceful exit"]
    S4["VISUALIZATION\nProcess logs\nSave plots"]
    S5["COMPLETE\nReview results\nin session folder"]

    S1 --> S2 --> S3 --> S4 --> S5
```

---

## File Organization

```
monitoring_sessions/
│
├── <timestamp>/              # Auto-generated session
│   ├── session_info.txt     # Metadata: time, node, options
│   ├── graph_timing.csv     # Raw timing data
│   ├── resource_usage.log   # Raw resource data
│   └── visualizations/      # Generated plots
│       ├── timing_*.png
│       └── resource_*.png
│
└── <custom_name>/           # Named session (--session flag)
    └── ... (same structure)
```

---

## Design Principles

| Principle | Description |
|-----------|-------------|
| Single Responsibility | Each script does one thing: orchestrate, monitor graph, monitor resources, or visualize |
| Composability | Scripts work independently or together via the orchestrator |
| Graceful Degradation | If one monitor fails, the other continues; raw data is always preserved |
| User Experience First | One command covers the common case; automatic session organization |
| Data Preservation | Raw data always saved; visualizations can be regenerated at any time |
