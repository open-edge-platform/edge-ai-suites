# Release Notes - Multi-Modal Patient Monitoring

## Version 1.0.0 - March 25, 2026

This is the initial release of the application, therefore, it is considered a preview version.

Multi-Modal Patient Monitoring showcases how a single Intel-powered edge system can
simultaneously run computer vision, physiological signal processing, artificial intelligence
inference, and real-time medical device telemetry — all within one integrated dashboard.

It proves that heterogeneous workloads — from 3D human pose estimation to heart-rate
extraction, AI-based ECG analysis, and medical device simulation — can coexist efficiently on
one platform without compromising performance or stability.


### New

The initial feature set of the application is now available:

- Heart and respiratory rate monitoring
- Integration with medical devices
- Pose estimation with joint tracking
- ECG analysis with 12-lead classification

### Known issues

- Docker fails with the `gathering device information` error.

  This may happen on systems without NPU. NPU is optional for use but is still defined as a
  possible accelerator in the image setup.

  To work around the issue, in `docker-compose.yaml`, remove the device by commenting out
  the following lines, like so:

  ```
  # devices:
  #   - /dev/dri
  #   - /dev/accel
  #   - /dev/accel/accel0
```