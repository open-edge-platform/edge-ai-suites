# Release Notes: Smart Route Planning Agent

## Version 1.0.0

**April 01, 2026**

The Smart Route Planning Agent (SRPA) is a new sample application which presents the use of
Hybrid AI in combination with the Smart Traffic Intersection Agent (STIA).
SRPA acts as the orchestration agent, accepting live input from multiple Smart Traffic
Intersection Agents and making routing decisions. It mimics a real-world deployment scenario,
where an orchestration agent on the cloud communicates with edge agents to accomplish a
particular goal. The goal for SRPA is to identify the most optimal route between two
points using the live traffic data provided by the STIA, which mimics the agent deployed
at the edge. A UI is provided to select two end points for the route, show recommended
route options, and get information from edge agents.

**New**

- **Real-time Traffic Analysis**: Comprehensive directional traffic density monitoring with MQTT integration.
- **VLM Integration**: Vision Language Model (VLM)-powered traffic scene analysis with sustained traffic detection.
- **Sliding Window Analysis**: 15-second sliding window with 3-second sustained threshold for accurate traffic state detection.
- **Camera Image Management**: Intelligent camera image retention and coordination between API and VLM services.
- **RESTful API**: Complete HTTP API for traffic summaries, intersection monitoring, and VLM analysis retrieval.
- **Concurrency Control**: Semaphore-based VLM worker management for optimal resource utilization.
  - **Impact**: Prevents VLM service overload and ensures reliable traffic analysis.
- **Image Retention Logic**: Camera images persist with VLM analysis for consistent data correlation.
  - **Impact**: API responses show actual images analyzed by VLM, improving traceability and debugging.
- **Enhanced Error Handling**: Comprehensive error management across MQTT, VLM, and image services.
  - **Impact**: Improved service reliability and diagnostic capabilities.

**Known Issues**

- Helm is not supported.
- This release includes only limited testing on Standalone and Developer Node versions
  of Edge Microvisor Toolkit, some behaviors may not yet be fully validated across all scenarios.
