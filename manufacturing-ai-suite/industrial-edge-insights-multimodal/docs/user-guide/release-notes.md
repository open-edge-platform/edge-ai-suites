# Release Notes: Industrial Edge Insights Multimodal

## Version 2026.0

**March 24, 2026**

This release introduces **S3-based frame storage**, **deployment hardening**, and
**documentation improvements**.

**New**

- **RTP Timestamp Alignment**: Fusion Analytics now uses the RTP sender NTP timestamp
  (`metadata.rtp.sender_ntp_unix_timestamp_ns`) to match frames with the nearest metadata
  records for improved synchronization.
- **SeaweedFS S3 Integration**: DL Streamer now stores output frames and images in an
  S3-compatible SeaweedFS backend, with full Helm chart support.
- **Vision Metadata Persistence**: DL pipeline vision metadata is now saved persistently to
  InfluxDB through Fusion Analytics for improved traceability.
- **Helm Deployment**: Helm charts for multimodal deployment are now available.

**Improved**

- Simulation data is now embedded directly into the container image, removing the external
  PV/PVC volume dependency and simplifying weld-data-simulator deployment.
- System requirements have been updated to reflect CPU-only validated configurations.
- Third-party service images have been updated: Telegraf, Grafana, Eclipse Mosquitto,
  MediaMTX, Coturn, and SeaweedFS.
- **Security**: SeaweedFS container runtime has been hardened.
- Documentation has been extended and improved for ease of navigation, covering updates to
  setup guides, Helm deployment, and more.


For information on older versions, check [release notes 2025](./release-notes/release-notes-2025.md)

<!--hide_directive
```{toctree}
:maxdepth: 5
:hidden:

release-notes/release-notes-2025.md
```
hide_directive-->