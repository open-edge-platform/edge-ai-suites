# Release Notes

## Current Release

**Version**: 2026.2.0 \
**Helm Chart Version**: 1.1.0 \
**Release Date**: 06 Aug 2026

**Changes**:

- Data Preparation:

  - Replaced the Milvus-specific data preparation microservice with the generic
    Multimodal DataPrep microservice, which is shared with other applications.
  - Media is embedded in place from the shared data mount, so ingesting a
    directory no longer stores a second copy of the media on disk.
  - Re-running an update against the same directory now skips already ingested
    files instead of duplicating them.
  - Object detection is disabled by default. Only full frames are indexed, which
    keeps search results free of crop duplicates. Set
    `MM_DATAPREP_ENABLE_OBJECT_DETECTION` and `DATA_INGEST_WITH_DETECT` to
    enable it.

- Helm Chart:

  - The chart is no longer tied to a namespace named `vsqa`. In-cluster service
    addresses are derived from the release namespace, so it can be installed
    into any namespace.
  - Added `resources` on the VLM, embedding, and data preparation services to
    request Intel device plugin resources when running on GPU or NPU.
  - The render device group is now applied to the pods, so a non-root container
    user can open `/dev/dri/renderD*`.
  - Added `global.nodeSelector` to pin the pods to the node that holds the
    host data path and the accelerator devices.

- Documentation:

  - Documented device selection, device plugin resources, device group ids,
    node pinning, and the corresponding troubleshooting steps for Helm.
  - VLM OpenVINO Serving is now consumed as a published image instead of being
    built from source.

**HW used for validation**:

- Intel® Core™ processors (13th Gen, i7 recommended)
- Intel® Arc™ A-Series Graphics (Intel® Arc™ A770 recommended)

## Previous Releases

**Version**: 2025.2.0 \
**Helm Chart Version**: 1.0.0 \
**Release Date**: 10 Dec 2025

**Features**:

- Visual Search:

  - Search images and videos using natural language queries.

- Question Answering:

  - Ask questions about selected media and receive context-aware answers.

- Microservices Architecture:

  - Includes data preparation, retriever, multimodal embedding, VLM serving, and a Streamlit-based web UI.

**HW used for validation**:

- Intel® Core™ processors (13th Gen, i7 recommended)
- Intel® Arc™ A-Series Graphics (Intel® Arc™ A770 recommended)
