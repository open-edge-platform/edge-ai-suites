# Blueprint

This page documents the minimum software stack that **HMI Augmented Worker** uses from the
broader Open Edge Platform (Edge AI Libraries, tools, and microservices), so you can see
exactly what is required to run this sample application versus what the platform additionally
offers. Unlike the other Manufacturing AI Suite sample applications, this one does not ship
its own Docker Compose stack — it composes an external RAG sample application with a
Windows®-hosted HMI, split across a Type-2 hypervisor host and a guest VM.

## Core Stack

| Category | Component | Role in this sample application |
|---|---|---|
| Host OS / hypervisor | Edge Microvisor Toolkit (EMT) | Type-2 hypervisor host running natively on Intel® Core™ hardware |
| Guest OS | Windows® OS VM | Hosts the HMI application and the File Watcher Service |
| RAG microservice | `Chat Question & Answer Core` (external Edge AI Libraries sample application) | Provides the full RAG pipeline (LLM, Embedding, Retriever, Reranker) consumed as-is by this sample application |
| Custom microservice | File Watcher Service (this repo, Windows-hosted) | Watches a knowledge-base folder and forwards new/changed files to `Chat Q&A Core` for ingestion |

> **Note:** `Chat Question & Answer Core` is deployed and configured independently — see its
> own [system requirements](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/chat-question-and-answer-core/get-started/system-requirements.html)
> for the specific microservices (LLM serving, embedding, retriever, reranker) it deploys.
> This repository does not modify or redeploy that stack.

## Stack Component System Requirements

Each shared component brings its own hardware/software requirements, documented at the
source rather than repeated here:

| Component | System Requirements |
|---|---|
| Chat Question & Answer Core | [System Requirements](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/chat-question-and-answer-core/get-started/system-requirements.html) |
| Edge Microvisor Toolkit (EMT) | [System Requirements](https://docs.openedgeplatform.intel.com/dev/edge-microvisor-toolkit/emt-system-requirements.html) |

## Optional Add-ons

None — this sample application does not define optional deployment add-ons beyond the
`Chat Q&A Core` configuration options (model/embedding/reranker choice), which are documented
in `Chat Q&A Core`'s own guides.

## Not Used by This Sample Application

The following platform capabilities are available on Open Edge Platform but are **not** part
of this sample application's stack: DL Streamer, OpenVINO™ vision pipelines, Intel® Geti™,
time-series analytics (TICK stack), and ROS-based robotics middleware.

## Supporting Resources

- [System Requirements](./get-started/system-requirements.md)
- [Get Started Guide](./get-started.md)
