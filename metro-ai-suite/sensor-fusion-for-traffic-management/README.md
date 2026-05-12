# Intel® Metro AI Suite Sensor Fusion for Traffic Management

This directory now contains two sensor-fusion implementations:

- `post-fusion/`: the original Sensor Fusion for Traffic Management codebase, now scoped to the post-fusion pipelines for camera + radar (C+R) and camera + lidar (C+L).
- `intermediate-fusion/`: the BEVFusion-based intermediate-fusion implementation.

## Choose an implementation

### Post-Fusion

Use this implementation for the original post-fusion traffic pipelines, including C+R and C+L variants.

- [Post-fusion README](./post-fusion/README.md)
- [Post-fusion user guide](./post-fusion/docs/user-guide/index.md)
- [Post-fusion get started guide](./post-fusion/docs/user-guide/get-started-guide.md)

### Intermediate-Fusion

Use this implementation for the BEVFusion-based intermediate-fusion deployment.

- [Intermediate-fusion README](./intermediate-fusion/README.md)
- [Intermediate-fusion Docker guide](./intermediate-fusion/docker/README_Docker.md)
- [Intermediate-fusion host guide](./intermediate-fusion/docs/GSG.md)

## Directory Layout

- `post-fusion/`: build scripts, runtime scripts, deployment assets, and user documentation for the post-fusion implementation.
- `intermediate-fusion/`: BEVFusion deployment assets, Docker workflow, smoke tests, and evaluation tools.