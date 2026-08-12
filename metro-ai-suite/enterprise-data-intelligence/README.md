<!--
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Enterprise Data Intelligence

An agent-native automation platform that combines a local knowledge base with autonomous agents to complete real enterprise tasks end-to-end. It wires together a UI service, retrieval-augmented generation (EC-RAG), an LLM router with prompt compression, and an OpenClaw agent runtime — agents run reusable Skills that query the knowledge base and produce professional deliverables (e.g. competitive-analysis reports).

## Skills

| Skill | Description | Status |
|-------|-------------|--------|
| `competitive_analysis_PDF_generator` | Competitive-analysis report generator — gathers product info from the local RAG knowledge base plus web search, then produces a professional Chinese HTML/PDF comparison report | Shipped (`SKILL.md` + `query_rag.sh`) |
| `knowledgebase` | Generic RAG query skill — retrieves any information from the local EC-RAG knowledge base via a curl-based `ecrag` wrapper and generates structured reports, summaries, comparisons, or Q&A responses | Shipped (`SKILL.md` + `ecrag`) |

See [skills/](skills/) for the shipped Skills and [docs/user-guide/](docs/user-guide/) for how to install and enable a Skill in OpenClaw.

## Architecture

The platform is built around a UI service that talks to the OpenClaw agent runtime. OpenClaw orchestrates work through Skills. A Skill retrieves grounded facts from the EC-RAG knowledge base, while an LLM Router (with a prompt compressor) fronts local and cloud models.

```
                 user
                  │
                  ▼
          ┌───────────────┐
          │      UI       │  :7000
          └───────┬───────┘
                  │
                  ▼
          ┌───────────────┐        Skills (competitive_analysis_PDF_generator)
          │   OpenClaw    │  :18789
          │   agent       │ ◄──────────────┐
          └───┬───────┬───┘                │ query_rag.sh
              │       │                     ▼
   model calls│       │            ┌────────────────┐
              ▼       │            │  EC-RAG        │  :16011
      ┌──────────────┐│            │  (retrieval +  │
      │  Router +    ││            │   vLLM answer) │
      │  compressor  ││ :8000/:8001└────────────────┘
      └──────┬───────┘│
             ▼        ▼
      local vLLM   cloud models
      :8086        (MiniMax, …)
```

### Components

- **UI** — browser-based front end for sending tasks to OpenClaw and viewing generated results.
- **Router + compressor** — LLM router that fronts local (vLLM) and cloud models, with a LinguaCompressor front end that shrinks prompts before dispatch.
- **EC-RAG** — Edge Craft RAG: embedding + reranker + vLLM answer generation over an uploadable knowledge base (Milvus vector store).
- **OpenClaw** — the agent runtime that loads Skills, calls models via the router, and executes tasks (web search, RAG query, PDF generation).
- **Skills** — reusable, self-contained task recipes under [skills/](skills/) that agents load at runtime.

## Get Started

Follow the setup guide to stand up all services and run the demo:

- [User Guide](docs/user-guide/get-started.md).

The guide walks through, in order:

1. **Router + compressor** — please refer to the [`inference-router`](https://github.com/open-edge-platform/edge-ai-libraries/tree/release-2026.2.0/microservices/inference-router) microservice.
2. **EC-RAG** — please refer to the [`agentic-rag`](../agentic-rag) directory.
3. **OpenClaw** — install OpenClaw, merge the provider/agent/skill config into `openclaw.json`, and install the repository Skills into the agent workspace.
4. **UI** — build and start the UI Docker Compose service, then open `http://<SERVER_HOST>:7000` to run the demo.

## License

See [LICENSE](LICENSE). This project is licensed under the Apache License 2.0.
