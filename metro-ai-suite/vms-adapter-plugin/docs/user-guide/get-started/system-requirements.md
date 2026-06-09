# System Requirements

The VMS Adapter Plugin itself is a lightweight orchestration service. Hardware requirements scale with the number of cameras and the AI Analytics Apps running alongside it (LVC, DLS Vision app like Loitering Detection) — refer to those applications' system requirements for GPU/NPU needs. So, the system requirements of the used analytics determine the platforms than VAP itself. The documentation here, hence, should be calibrated depending on the analytics used.

## Supported Platforms

**Operating Systems**

- Ubuntu 22.04 LTS
- Ubuntu 24.04 LTS

**Hardware Platforms**

- 12th Generation Intel® Core™ processor or above
- Intel® Xeon® Scalable Processors (4th Gen or above)

## Minimum Requirements

| **Component**   | **Minimum**                      | **Recommended**                          |
|-----------------|----------------------------------|------------------------------------------|
| **Processor**   | 12th Gen Intel® Core™            | Intel® Core™ Ultra Processors (Series 2) |
| **Memory**      | 8 GB                             | 16 GB                                    |
| **Disk Space**  | 20 GB                            | 64 GB                                    |


## Software Requirements

| **Component**         | **Version**        |
|-----------------------|--------------------|
| Docker Engine         | 27.3.1 or higher   |
| Docker Compose        | 2.x or higher      |
| Git                   | Any recent version |

## Network / Ports

Default ports (configurable via `.env`):

| **Service**          | **Default Port** | **Purpose**                          |
|----------------------|------------------|--------------------------------------|
| Backend API          | `8085`           | REST API and Swagger UI              |
| Provider Dashboard   | `3100`           | React UI (nginx)                     |
| PostgreSQL           | `5433`           | Internal database (host-mapped)      |
| Frigate UI           | `5000`           | Frigate camera management (optional) |

> Ensure these ports are not in use by other services before starting the stack.

## Connected Service Requirements

The following external services must be reachable from the VAP backend container at startup:

| **Service**                     | **Required For**             | **Default Port** |
|---------------------------------|------------------------------|------------------|
| Live Video Captioning (LVC)     | LVC Analytics App integration     | `4173`           |
| MediaMTX (WebRTC signaling)     | Live stream relay to UI       | `8889`           |
| Nx Witness                      | Nx VMS camera discovery       | `7001` (HTTPS)   |
| DLStreamer Pipeline Server (dls_vision)| DLStreamer Vision       | `8080`           |
| MQTT Broker                     | dls_vision metadata streaming        | `1883`           |

## Validation

Proceed to [Get Started](../get-started.md) once Docker is installed and your VMS and Analytics App services are reachable.
