# Build from Source

Live Video Search depends on **VSS Search** and **Smart NVR** images. Follow the official build guides below and then use `REGISTRY_URL`/`TAG` to reference your built images.

## Build VSS Images

- VSS build guide (public):
 [How to Build from Source](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/sample-applications/video-search-and-summarization/docs/user-guide/build-from-source.md)

## Build Smart NVR Images

- Smart NVR build guide:
 [How to Build from Source](../../../../smart-nvr/docs/user-guide/how-to-build-from-source.md)

## Match Image Tags

Ensure `REGISTRY_URL` and `TAG` match the images you built or pushed:

```bash
export REGISTRY_URL=<registry-prefix>
export TAG=<image-tag>
```
