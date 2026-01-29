# Industrial Edge Insights - Multimodal

MultiModal Weld Defect Detection sample application demonstrates how to use AI
at the edge to identify defects in manufacturing environments by analyzing both
image and time series sensor data.

By combining results from image-based defect detection and time series anomaly
detection using logical "AND" or "OR" operations, the system provides:

- more robust and accurate identification of potential defects,
- enhances reliability, reduces false positives, and supports smarter
  decision-making for maintenance,
- helps manufacturers enhance product quality, reduce inspection time, and
  minimize costly rework by enabling proactive defect detection on the
  factory floor.

Industrial quality relies on safety and reliability, and manual inspections
are time-consuming and prone to human error. Therefore, we have developed the
application to leverage deep learning models to automate defect detection,
improving both accuracy and efficiency.

**Key features include:**

- Multi-modal data fusion: Combines visual inspection (images) and sensor data
  (such as current, voltage, and temperature) for comprehensive defect detection.
- Real-time inference: Processes data at the edge for immediate feedback and
  reduced latency.
- Configurable alerts: Notifies operators of detected defects to enable
  timely intervention.
- Extensible pipeline: Supports integration with additional data sources
  and models.

[The application](./weld-defect-detection/index.md) utilizes camera-based
visual inspection and sensor data analysis to identify anomalies in welding data.

<!--hide_directive
:::{toctree}
:hidden:

get-started.md
how-to-guides.md
weld-defect-detection/index.md
troubleshooting.md
release-notes.md

:::
hide_directive-->
