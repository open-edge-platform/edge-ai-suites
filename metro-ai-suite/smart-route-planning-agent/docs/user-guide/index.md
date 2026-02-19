# Smart Route Planning Agent

The Smart Route Planning Agent is an AI-powered route optimization agent that uses multi-agent
communication to analyze traffic intersections and find incident-free paths between source and
destination in real-time.

## Use Cases and Key Features

**Real-time Route Optimization**: Analyze multiple routes between source and destination to
find the optimal path based on live traffic conditions.

**Incident Avoidance**: Identify and avoid routes potentially affected by congestion, weather,
roadblocks, or accidents.

**Multi-Agent Traffic Analysis**: Communicates with [Smart Traffic Intersection Agent](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/smart-traffic-intersection-agent/index.html)
to gather live analysis reports for informed routing decisions.

## How It Works

The agent receives source and destination inputs, finds the shortest route from available
routes, queries traffic intersection agents for live reports, and determines the optimal route.

![System Architecture Diagram](./_assets/ITS_architecture.png)

### Data Flow

```
User Input (Source/Destination) → Route Planning Agent
                                  ├─→ Find Shortest Route (from GPX files)
                                  ├─→ Query Traffic Intersection Agents
                                  ├─→ Analyze Route Conditions
                                  └─→ Return Optimal Route
```

## Learn More

- [System Requirements](./get-started/system-requirements.md)
- [Get Started](./get-started.md)
- [Release Notes](./release-notes.md)

<!--hide_directive
:::{toctree}
:hidden:

get-started
release-notes

:::
hide_directive-->
