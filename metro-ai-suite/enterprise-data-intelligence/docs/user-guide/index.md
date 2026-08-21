# Enterprise Data Intelligence

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/enterprise-data-intelligence">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/enterprise-data-intelligence/README.md">
     Readme
  </a>
</div>
hide_directive-->

An agent-native automation platform that combines a local knowledge base with autonomous
agents to complete real enterprise tasks end-to-end. It wires together a UI service,
retrieval-augmented generation (EC-RAG in this case), an LLM router with prompt compression,
and an OpenClaw agent runtime — agents run reusable Skills that query the knowledge base and
produce professional deliverables (e.g., competitive-analysis reports).

## Features

- **Multi-agent task automation** — OpenClaw runs a main agent that can spawn sub-agents to
  complete multi-step enterprise tasks without manual intervention.
- **Local knowledge base retrieval** — EC-RAG indexes uploaded documents in a Milvus vector
  store and serves grounded answers through embedding, reranking, and vLLM-based generation.
- **Hybrid model routing with cost savings** — The Router and compressor front local (vLLM)
  and cloud models (for example, MiniMax), shrinking prompts before dispatch to cut token
  usage and latency.
- **Token consumption monitoring** — The UI shows a live dashboard of local versus cloud
  token usage, latency, and tokens saved by compression.
- **Reusable Skills** — Agents load self-contained Skills, such as the competitive-analysis
  report generator, to produce professional deliverables like HTML and PDF reports.
- **Conversational UI** — A chat interface with slash commands (for example, `/model`,
  `/session`, `/tool`) and streaming responses for controlling agents and models
  mid-conversation.
- **Multi-language support** — The UI and generated reports support multiple languages,
  including English and Chinese.

## Skills

| Skill | Description | Status |
| ----- | ----------- | ------ |
| `competitive_analysis_PDF_generator` | Competitive-analysis report generator — gathers product info from the local RAG knowledge base plus web search, then produces a professional Chinese HTML/PDF comparison report | Shipped (`SKILL.md` + `query_rag.sh`) |
| `knowledgebase` | Generic RAG query skill — retrieves any information from the local EC-RAG knowledge base via a curl-based `ecrag` wrapper and generates structured reports, summaries, comparisons, or Q&A responses | Shipped (`SKILL.md` + `ecrag`) |

See the [skills folder](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/enterprise-data-intelligence/skills)
for the shipped Skills and the [Get Started guide](./get-started.md) for how to install and
enable a Skill in OpenClaw.

## Architecture

The platform is built around a UI service that talks to the OpenClaw agent runtime. OpenClaw
orchestrates work through Skills. A Skill retrieves grounded facts from the EC-RAG knowledge
base, while an LLM router (with a prompt compressor) fronts local and cloud models.

```text
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
- **Router + compressor** — LLM router that fronts local (vLLM) and cloud models, with a
  LinguaCompressor front end that shrinks prompts before dispatch.
- **EC-RAG** — Edge Craft RAG: embedding + reranker + vLLM answer generation over an
  uploadable knowledge base (Milvus vector store).
- **OpenClaw** — the agent runtime that loads Skills, calls models via the router, and
  executes tasks (web search, RAG query, PDF generation).
- **Skills** — reusable, self-contained task recipes under the
  [skills folder](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/enterprise-data-intelligence/skills)
  that agents load at runtime.

## Additional Resources

- [Inference Router microservice](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/inference-router/index.html) — the microservice that implements the Router and compressor.
- [Get Started guide](./get-started.md) — step-by-step instructions for setting up the
  platform and running the demo.
- [Release Notes](./release-notes.md) — a changelog of updates and improvements to the platform.

<!--hide_directive
:::{toctree}
:hidden:

get-started.md
Release Notes <release-notes.md>

:::
hide_directive-->
