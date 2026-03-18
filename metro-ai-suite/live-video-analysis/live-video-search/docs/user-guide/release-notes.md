# Release Notes: Live Video Search

## Version 1.0.0

**April 01, 2026**

Live Video Search is a new sample application which implements embedding and
visual data ingestion microservices (available in
[Edge AI Libraries](https://docs.openedgeplatform.intel.com/2026.0/ai-libraries.html))
for processing RTSP camera streams and user query-based search. The application
converts the input camera data to embeddings continuously, using models like Clip.
The embeddings are stored in a Vector Database (VectorDB ) and enable search on
live camera feed and historical video data.
A rich UI is provided to configure the camera used for data ingestion, enter
the search query, and view telemetry data, currently, for CPU, GPU, and memory
utilization. The sample application introduces camera streaming with Frigate.

**New**

- Live Video Search stack integrating Smart NVR with VSS Search.
- Time‑range filtering in search via UI or natural‑language query parsing.
- Telemetry visualization in VSS UI for live system performance.

**Known Issues/Limitations**

- Deploy with Helm is not yet supported for Live Video Search.
- First‑time model downloads may take several minutes.
- Time‑range queries require the clock and timezone on the host to be accurate.

> *The application has been validated on Intel® Xeon® 5 + Intel® Arc&trade; B580 GPU.*
