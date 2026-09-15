# Release Notes: Enterprise Data Intelligence

## Version 2026.2.0

**Release Date**: September 9, 2026

This initial release introduces an agent-native automation platform that combines a local
knowledge base with autonomous agents to complete enterprise tasks end-to-end.

**New**:

- **Integrated agent workflow**: connects a browser-based UI, the OpenClaw agent runtime,
  EC-RAG, and an LLM router with prompt compression in a unified enterprise task workflow.
- **Grounded knowledge retrieval**: uses EC-RAG to retrieve information from an uploadable
  local knowledge base and generate answers grounded in enterprise data.
- **Reusable OpenClaw Skills**: includes a generic `knowledgebase` Skill for queries,
  summaries, comparisons, and structured reports, plus a `competitive_analysis_PDF_generator` Skill for specialized analysis.
- **Competitive-analysis reports**: combines information from the local knowledge base with
  web search to generate professional Chinese HTML and PDF comparison reports.
- **Flexible model access**: routes agent model calls to local vLLM or cloud models and uses
  LinguaCompressor to reduce prompts before dispatch.
- **Containerized UI**: provides a Docker Compose deployment for submitting tasks to OpenClaw
  and viewing generated results in a browser.
