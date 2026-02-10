# Smart Tolling Application

The **Metro Smart Tolling Application** is a high-precision Edge AI solution designed to revolutionize automated tolling. By fusing multi-camera inputs (Front, Rear, and Side profiles), the system delivers accurate vehicle detection and classification, license plate detection, color classification, axle counting and tariffing.

Enabling such use cases across multiple viewpoints helps in understanding the object interaction with the real world in 3-D space. All the components used run on a single system enabling low latency, simplified deployment and cost efficiency.

![Smart Tolling System Architecture](./docs/user-guide/_assets/smart_tolling_architecture.png)

## Use Cases

- **Vehicle Axle Detection**: Determines vehicle class based on axle and wheel count
  - Usage: Used for toll classification and revenue calculation.
- **License Plate Detection**: Identifies vehicles uniquely using license plates
  - Usage: Used for reading vehicle license plate text from both front and rear views.
- **Visualization & Analytics**:Provides real-time and historical insights for toll operators.

## Key Benefits

- **Accuracy**: Multi view accuracy.
- **Revenue Protection**: Advanced "Lift Axle" detection using Computer Vision allows for accurate tariffing.
- **Audit Compliance**: Every transaction includes an "Image Evidence" for simplified auditing.

## How it Works

The system uses the **Metro Edge Architecture** based on three key principles:

1. **Perception**: Deep Learning Streamer (DLStreamer) processes 3/4 camera feeds.
2. **Control**: SceneScape Controller aggregates metadata.
3. **Analytics**: Node-RED transforms events into traffic insights (Traffic Volume, Flow Efficiency, Tariffing).

For more details, refer to [How it Works](./docs/user-guide/how-it-works.md).

## Learn More

- [System Requirements](./docs/user-guide/get-started/system-requirements.md): Hardware, OS and Software Prerequisites.
- [Get Started](./docs/user-guide/get-started.md): Installation, Configuration and Launch steps.
- [Technical Reference](./docs/user-guide/how-it-works/technical-reference.md): Engineering Specs, Zero-Copy Pipeline and API usage.
- [Troubleshooting](./docs/user-guide/troubleshooting.md): Solutions to common issues.

## License

Metro Vision AI - Internal Use Only.
