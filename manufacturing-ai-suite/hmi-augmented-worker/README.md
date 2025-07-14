# HMI Augmented Worker

GenAI is transforming Human Machine Interfaces (HMI) by enabling more intuitive, conversational, and context-aware interactions between operators and industrial systems. By leveraging advanced language models and retrieval-augmented generation, GenAI enhances decision-making, streamlines troubleshooting, and delivers real-time, actionable insights directly within the HMI environment. This leads to improved operator efficiency, reduced downtime, and safer manufacturing operations.

The `HMI Augmented Worker` sample application show cases how RAG pipelines can be integrated with HMI application. Besides RAG, the key feature of this sample application is that it executes in a Hypervisor based setup where HMI application executes on Windows® OS based VM while the RAG application runs in native Ubuntu or EMT based setup. This enables running this application on Intel® Core&trade; portfolio. 

## Documentation

- **Overview**

  - [Overview](./docs/user-guide/overview.md): High-level introduction.
  - [Architecture](./docs/user-guide/overview.md#high-level-architecture): High-level architecture.

- **Getting Started**
  - [Get Started](./docs/user-guide/get-started.md): Setup guides to getting started with the sample appplication.
  - [System Requirements](./docs/user-guide/system-requirements.md): Requirements include hardware and software to deploy the sample application.

- **Advanced**
  - [Build From Source](./docs/user-guide/how-to-build-from-source.md): Guide to build the file watcher service on Windows® OS and how it can be interfaced with RAG pipeline that executes on the Ubuntu or EMT side.

- **Release Notes**
  - [Release Notes](./docs/user-guide/release_notes/overview.md): Notes on the latest releases, updates, improvements, and bug fixes.