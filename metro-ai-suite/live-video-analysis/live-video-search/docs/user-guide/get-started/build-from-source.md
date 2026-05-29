# Build from Source

Live Video Search depends on **VSS Search** and **Smart NVR** images. Follow the official build guides below and then use `REGISTRY_URL`/`TAG` to reference your built images.

## Build VSS Images

- VSS build guide:
 [How to Build from Source](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/video-search-and-summarization/build-from-source.html)

## Build Smart NVR Images

- Smart NVR build guide:
 [How to Build from Source](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/smart-nvr/get-started/build-from-source.html)

## Match Image Tags

Ensure `REGISTRY_URL` and `TAG` match the images you built or pushed:

```bash
export REGISTRY_URL=<registry-prefix>
export TAG=<image-tag>
```
