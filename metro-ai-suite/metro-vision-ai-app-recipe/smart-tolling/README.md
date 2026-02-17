# Smart Tolling Application

The **Metro Smart Tolling Application** is a high-precision Edge AI solution designed to revolutionize automated tolling. By fusing multi-camera inputs (Front, Rear, and Side profiles), the system delivers accurate vehicle detection and classification, license plate detection, color classification, axle counting and tariffing.

Enabling such use cases across multiple viewpoints helps in understanding the object interaction with the real world in 3-D space. All the components used run on a single system enabling low latency, simplified deployment and cost efficiency.

![Smart Tolling System Architecture](./docs/user-guide/_assets/smart_tolling_architecture.png)

## Key Features

**Multi vision**: Scene-based analytics allow insights beyond single sensor views.

- **Vehicle axle detection**:

  Vehicle class is determined based on axle and wheel count. Intended for toll
  classification, as well as revenue calculation and protection.

- **Lift axle detection**:

  The type of axle is determined based on camera feed. Ensures accurate tariffing,
  as lift axles may affect toll classification even when raised.

- **License plate detection**:

  The application identifies vehicles uniquely by their license plates, which are
  read from both front and rear views. The image evidence is included in every
  transaction for simplified auditing.

**Visualization & analytics**: Provides real-time and historical insights for
toll operators.

**Modularity**: Architecture based on modular microservices enables composability
and reconfiguration.

**High-throughput processing**: [Optimized video pipelines](./docs/user-guide/how-it-works/optimization.md#zero-copy-video-pipeline)
for Intel edge devices.

## How it Works

The system uses the **Metro Edge Architecture** based on three key principles:

- **Perception**: Deep Learning Streamer (DLStreamer) [processes 3/4 camera feeds](./docs/user-guide/how-it-works/perception-layer.md).
- **Control**: SceneScape Controller [aggregates metadata](./docs/user-guide/how-it-works.md#analytics-pipeline-downstream).
- **Analytics**: Node-RED [transforms events into traffic insights](./docs/user-guide/how-it-works/analytics-pipeline.md#node-red-transformation)
  (Traffic Volume, Flow Efficiency, Tariffing).

## Learn More

- [System Requirements](./docs/user-guide/get-started/system-requirements.md)
- [Get Started](docs/user-guide/get-started.md)
- [How It Works](./docs/user-guide/how-it-works.md)
- [Troubleshooting](./docs/user-guide/troubleshooting.md)

## License

Metro Vision AI - Internal Use Only.
