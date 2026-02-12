# Smart Tolling Application

The **Metro Smart Tolling Application** is a high-precision Edge AI solution
designed to revolutionize automated tolling. By fusing multi-camera inputs
(Front, Rear, and Side profiles), the system delivers accurate vehicle detection
and classification, license plate detection, color classification,
axle counting and tariffing.

Enabling such use cases across multiple viewpoints helps in understanding the
object interaction with the real world in 3-D space. All the components used
run on a single system enabling low latency, simplified deployment and cost
efficiency.

## Key Features

**Multi vision**:

Scene-based analytics allow insights beyond single sensor views.

- **Vehicle axle detection**:

  Vehicle class is determined based on axle and wheel count.\
  Intended for toll classification, as well as revenue calculation and protection.\
  Multi view and the advanced "lift axle" detection using computer vision
  ensures accurate tariffing.

- **License plate detection**:

  The application identifies vehicles uniquely by their license plates, which are
  read from both front and rear views.\
  The image evidence is included in every transaction for simplified auditing.

**Visualization & analytics**:

Provides real-time and historical insights for toll operators.

**Modularity**:

Architecture based on modular microservices enables composability and reconfiguration.

**High-throughput processing**:

[Optimized video pipelines](./how-it-works.md) for Intel edge devices.

## How it Works

The system uses the **Metro Edge Architecture** based on three key layers:

- **Perception**: Deep Learning Streamer (DLStreamer) [processes 3/4 camera feeds](./perception-layer.md).
- **Control**: SceneScape Controller [aggregates metadata](./how-it-works.md#analytics-pipeline-downstream).
- **Analytics**: Node-RED [transforms events into traffic insights](./how-it-works.md#node-red-transformation)
  (Traffic Volume, Flow Efficiency, Tariffing).

## Learn More

- [System Requirements](./get-started/system-requirements.md)
- [Get Started](./get-started.md)
- [How it works](./how-it-works.md)
- [Troubleshooting](./troubleshooting.md)

<!--hide_directive
:::{toctree}
:hidden:

get-started
how-it-works
api-reference
troubleshooting

:::
hide_directive-->
